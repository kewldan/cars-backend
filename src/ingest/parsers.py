import json
import logging
import re
import time
from typing import Protocol

import aiohttp
from pydantic import BaseModel

from settings import settings

log = logging.getLogger(__name__)


class ParsedCar(BaseModel):
    is_listing: bool = True
    make: str = ""
    model: str = ""
    year: int = 0
    vin: str = ""
    fuel: str = "Бензин"
    engine: float = 0.0
    power: int = 0
    mileage: int = 0
    transmission: str = "Автомат"
    drive: str = "Передний"
    body: str = "Седан"
    color: str = ""
    city: str = ""
    price: int = 0
    sold: bool = False
    summary: str = ""
    description: str = ""
    features: list[str] = []


class Parser(Protocol):
    async def parse(self, text: str) -> ParsedCar | None: ...


class QwenParser:
    """LLM-based parser. Hits an OpenAI-compatible chat-completions endpoint
    (Ollama, vLLM, LM Studio, llama.cpp server, ...).
    """

    SYSTEM_PROMPT = (
        "You are a parser for car-for-sale posts from Georgian (country) Telegram channels. "
        "The input is a single Telegram post. Extract structured data about the car.\n\n"
        "OUTPUT: a single JSON object. No markdown fences, no commentary, no trailing text. "
        "Use null for fields that are not stated in the post — never guess.\n\n"
        "SCHEMA (all keys required, values may be null):\n"
        "{\n"
        '  "is_listing": boolean,         // false if the post is not a car-for-sale ad (rental, parts, service, channel meta, etc.)\n'
        '  "make":         string|null,   // manufacturer in English Title Case, e.g. "Toyota", "Mercedes-Benz"\n'
        '  "model":        string|null,   // model + trim as written on the title line, e.g. "Outback Limited", "Wrangler Unlimited High Altitude 4xe", "Jetta S", "Q8 S line Premium Plus"\n'
        '  "year":         integer|null,  // model/production year, 1980..2031; if input is "MM/YYYY" output just YYYY\n'
        '  "vin":          string|null,   // 17-character VIN, uppercase, no spaces; only if explicitly printed in the post\n'
        '  "fuel":         "Бензин"|"Дизель"|"Гибрид"|"Электро"|"Газ"|null,\n'
        '  "engine":       number|null,   // displacement in liters as float, e.g. 2.0; ignore "TSI"/"TFSI"/"TDI"/"L"/"hybrid" suffix on the same line\n'
        '  "power":        integer|null,  // horsepower (л.с.); also pick up "(380hp)" or "380 л.с." written next to the engine\n'
        '  "mileage":      integer|null,  // odometer in kilometers; convert from miles if needed\n'
        '  "transmission": "Механика"|"Автомат"|"Робот"|"Вариатор"|null,\n'
        '  "drive":        "Передний"|"Задний"|"Полный"|null,\n'
        '  "body":         "Седан"|"Хэтчбек"|"Универсал"|"Кроссовер"|"Внедорожник"|"Купе"|"Минивэн"|"Пикап"|null,\n'
        '  "color":        string|null,   // colour in Russian, lowercase, e.g. "белый"\n'
        '  "city":         "Тбилиси"|"Батуми"|"Кутаиси"|"Рустави"|"Гори"|"Зугдиди"|"Поти"|"Телави"|null,\n'
        '  "price":        integer|null,  // price in USD; convert if posted in GEL (≈0.37 USD) or EUR (≈1.05 USD); ignore monthly-installment numbers and parenthetical alt prices like "(my avto 33000$)"\n'
        '  "sold":         boolean,       // true if the post (or its UPDATE block) says the car is sold/reserved/withdrawn ("продан","продана","sold","зарезервирован","снято с продажи"); false otherwise\n'
        '  "summary":      string|null,   // ≤80 chars, Russian, suitable as a card title (e.g. "Subaru Outback Limited 2023, 2.5L, AWD")\n'
        '  "description":  string|null,   // free-text Russian body about the car, cleaned of header lines, footer, URLs, phones, @usernames, emoji\n'
        '  "features":     string[]       // short Russian feature tags, e.g. ["панорама","кожа","камера 360","адаптивный круиз","Harman Kardon"]\n'
        "}\n\n"
        "INPUT FORMAT — many posts use this structured English-key header followed by a Russian description and a price/links footer:\n"
        "  Make Model Trim\n"
        "  Year: MM/YYYY (or YYYY)\n"
        "  Mileage: NNNNN km\n"
        "  VIN: 17-char VIN\n"
        "  Engine: 2.0L  /  1.4 TSI  /  2.0 (Plug-in hybrid 380hp)  /  3.0 mild hybrid\n"
        "  Drive: AWD | FWD | RWD | 4WD\n"
        "  City: Tbilisi | Batumi | Kutaisi | Rustavi | Gori | Zugdidi | Poti | Telavi\n"
        "When that header is present, use it as the source of truth for those fields.\n\n"
        "RULES:\n"
        "- If the post advertises multiple cars, parse only the FIRST.\n"
        "- If the post is not a car-for-sale ad, return {\"is_listing\": false} and null/empty for all other fields.\n"
        "- Never invent data. If something isn't stated, the value is null.\n"
        "- If the input is split into '=== ORIGINAL POST ===' and '=== UPDATE (newer reply) ===' blocks, the UPDATE block is authoritative for any field it restates (price, sold, mileage, etc.). Use the ORIGINAL block only as fallback for fields the UPDATE doesn't touch.\n"
        "- Year \"MM/YYYY\" → just YYYY (e.g. \"03/2023\" → 2023).\n"
        "- VIN: copy verbatim, uppercase, only if the post prints a 17-char VIN.\n"
        "- Engine line: take the leading number as displacement liters; if HP is given inline (e.g. \"(380hp)\"), set `power` from it.\n"
        "- Fuel cues: TSI/TFSI/MPI → Бензин; TDI → Дизель; \"hybrid\"/\"mild hybrid\"/\"plug-in hybrid\"/\"PHEV\" → Гибрид; \"EV\"/\"electric\"/\"BEV\" → Электро.\n"
        "- Drive mapping: AWD / 4WD / Quattro / 4Matic / xDrive → Полный; FWD → Передний; RWD → Задний.\n"
        "- City mapping (English → Russian): Tbilisi→Тбилиси, Batumi→Батуми, Kutaisi→Кутаиси, Rustavi→Рустави, Gori→Гори, Zugdidi→Зугдиди, Poti→Поти, Telavi→Телави.\n"
        "- Price: take the number after the 💵 emoji or \"$\". Ignore parenthetical alt prices like \"(my avto NNNN$)\" and ignore numbers describing monthly installments.\n"
        "- description: drop the structured English-key header AND the footer (price line, phone/@username, \"Auction link\" line, t.me/wa.me/viber/bid.cars URLs, channel promo blocks like \"GD MOTORS\" / \"Грузинская Лавка\"). Keep only the Russian free-text body that describes the car.\n"
        "- Strip phone numbers, @usernames, all URLs, and emoji from `description`.\n"
        "- Output VALID JSON only."
    )

    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
        timeout: int | None = None,
        thinking: bool | None = None,
    ) -> None:
        self.base_url = (base_url or settings.QWEN_BASE_URL).rstrip("/")
        self.model = model or settings.QWEN_MODEL
        self.timeout = timeout if timeout is not None else settings.QWEN_TIMEOUT
        self.thinking = thinking if thinking is not None else settings.QWEN_THINKING

    @property
    def _system_prompt(self) -> str:
        return self.SYSTEM_PROMPT if self.thinking else self.SYSTEM_PROMPT + "\n\n/no_think"

    async def parse(self, text: str) -> ParsedCar | None:
        if not text or not text.strip():
            return None
        prompt = text.strip()
        log.info("qwen → input (%d chars): %s", len(prompt), prompt[:200].replace("\n", " ⏎ "))
        timeout = aiohttp.ClientTimeout(total=self.timeout)
        body_payload: dict[str, object] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": self._system_prompt},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0,
        }
        if not self.thinking:
            body_payload["chat_template_kwargs"] = {"enable_thinking": False}
        t0 = time.monotonic()
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(
                f"{self.base_url}/chat/completions",
                json=body_payload,
            ) as resp:
                status = resp.status
                body = await resp.text()
        elapsed_ms = (time.monotonic() - t0) * 1000
        log.info("qwen ← HTTP %d in %.0fms (%d bytes)", status, elapsed_ms, len(body))
        if status >= 400:
            log.error("qwen error body: %s", body[:1000])
            raise RuntimeError(f"qwen HTTP {status}: {body[:500]}")
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            log.error("qwen non-JSON body: %s", body[:1000])
            raise
        if "choices" not in payload:
            err = payload.get("error") or payload
            log.error("qwen no choices in payload: %r", err)
            raise RuntimeError(f"Qwen endpoint returned no choices: {err!r}")
        content = payload["choices"][0]["message"]["content"]
        content = re.sub(r"<think>[\s\S]*?</think>", "", content, flags=re.IGNORECASE).strip()
        log.info("qwen ← raw content (%d chars): %s", len(content), content[:1500])
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            m = re.search(r"\{[\s\S]*}", content)
            if not m:
                log.error("qwen content has no JSON object")
                raise
            data = json.loads(m.group(0))
            log.info("qwen ← extracted JSON from wrapped content")
        log.info("qwen ← parsed: %s", data)
        if data.get("is_listing") is False:
            return None
        scrubbed = {k: v for k, v in data.items() if v is not None}
        return ParsedCar(**scrubbed)
