import json
import re
from typing import Protocol

import aiohttp
from pydantic import BaseModel

from settings import settings

KNOWN_MAKES: list[str] = [
    "Toyota", "Honda", "Mazda", "Nissan", "Subaru", "Mitsubishi", "Lexus", "Infiniti",
    "Suzuki", "Acura", "Daihatsu", "Isuzu",
    "BMW", "Mercedes-Benz", "Mercedes", "Audi", "Volkswagen", "Porsche", "Opel",
    "Skoda", "Seat", "MINI", "Smart",
    "Ford", "Chevrolet", "Dodge", "Jeep", "Cadillac", "Chrysler", "GMC", "Lincoln",
    "Buick", "Tesla",
    "Hyundai", "Kia", "Genesis", "SsangYong",
    "Renault", "Peugeot", "Citroen", "Dacia", "DS",
    "Fiat", "Alfa Romeo", "Lancia", "Ferrari", "Maserati", "Lamborghini", "Bugatti",
    "Volvo", "Saab", "Land Rover", "Range Rover", "Jaguar",
    "Lada", "GAZ", "UAZ", "Moskvich",
    "Geely", "Chery", "Haval", "BYD", "Great Wall", "Lifan", "Changan", "MG",
]

_FUEL_HINTS = {
    "Бензин": ["бензин", "petrol", "gasoline", "gas"],
    "Дизель": ["дизель", "diesel"],
    "Гибрид": ["гибрид", "hybrid"],
    "Электро": ["электро", "electric", "ev"],
    "Газ": ["газ", "lpg", "cng"],
}
_TRANS_HINTS = {
    "Автомат": ["автомат", "akpp", "акпп", "at"],
    "Механика": ["механика", "mkpp", "мкпп", "manual"],
    "Робот": ["робот", "dsg", "amt"],
    "Вариатор": ["вариатор", "cvt"],
}
_DRIVE_HINTS = {
    "Полный": ["4wd", "awd", "полный", "4x4", "4matic", "quattro", "xdrive"],
    "Передний": ["передний", "fwd", "ff"],
    "Задний": ["задний", "rwd", "fr"],
}
_BODY_HINTS = {
    "Седан": ["седан", "sedan"],
    "Хэтчбек": ["хэтчбек", "hatchback", "хетчбек"],
    "Универсал": ["универсал", "wagon", "estate"],
    "Кроссовер": ["кроссовер", "crossover"],
    "Внедорожник": ["внедорожник", "suv", "джип"],
    "Купе": ["купе", "coupe"],
    "Минивэн": ["минивэн", "minivan", "van"],
    "Пикап": ["пикап", "pickup"],
}
_COLOR_HINTS = [
    "белый", "чёрный", "черный", "серый", "серебристый", "красный", "синий",
    "зелёный", "зеленый", "жёлтый", "желтый", "оранжевый", "коричневый",
    "бежевый", "золотой", "фиолетовый", "розовый",
]
_GE_CITIES = [
    ("Тбилиси", ["тбилиси", "tbilisi"]),
    ("Батуми", ["батуми", "batumi"]),
    ("Кутаиси", ["кутаиси", "kutaisi"]),
    ("Рустави", ["рустави", "rustavi"]),
    ("Гори", ["гори", "gori"]),
    ("Зугдиди", ["зугдиди", "zugdidi"]),
    ("Поти", ["поти", "poti"]),
    ("Телави", ["телави", "telavi"]),
]


class ParsedCar(BaseModel):
    is_listing: bool = True
    make: str = ""
    model: str = ""
    year: int = 0
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
    summary: str = ""
    description: str = ""
    features: list[str] = []


class Parser(Protocol):
    async def parse(self, text: str) -> ParsedCar | None: ...


class HeuristicParser:
    """Best-effort regex parser used until the Qwen pipeline is wired up.

    Returns None when the post has no recognisable car-listing signal
    (no make AND no year AND no price).
    """

    _price_re = re.compile(r"(?:\$|USD\s*|usd\s*)\s*(\d[\d\s.,]{1,9})|(\d[\d\s.,]{1,9})\s*\$")
    _year_re = re.compile(r"\b(19[8-9]\d|20[0-3]\d)\b")
    _mileage_re = re.compile(r"(\d[\d\s.,]{0,9})\s*(?:км|km)\b", re.IGNORECASE)
    _engine_re = re.compile(r"\b(\d(?:[.,]\d)?)\s*(?:л\b|L\b|liters?|литр)", re.IGNORECASE)
    _power_re = re.compile(r"(\d{2,4})\s*(?:л\.?\s*с\.?|hp|лс)", re.IGNORECASE)

    @staticmethod
    def _to_int(raw: str) -> int:
        digits = re.sub(r"[^\d]", "", raw)
        return int(digits) if digits else 0

    @classmethod
    def _match_dict(cls, text: str, hints: dict[str, list[str]]) -> str | None:
        low = text.lower()
        for canonical, needles in hints.items():
            for n in needles:
                if n in low:
                    return canonical
        return None

    async def parse(self, text: str) -> ParsedCar | None:
        if not text or not text.strip():
            return None
        clean = text.strip()
        low = clean.lower()
        car = ParsedCar()

        if m := self._price_re.search(clean):
            car.price = self._to_int(m.group(1) or m.group(2) or "")
        if m := self._year_re.search(clean):
            car.year = int(m.group(1))
        if m := self._mileage_re.search(clean):
            car.mileage = self._to_int(m.group(1))
        if m := self._engine_re.search(clean):
            try:
                car.engine = float(m.group(1).replace(",", "."))
            except ValueError:
                pass
        if m := self._power_re.search(clean):
            car.power = int(m.group(1))

        for make in KNOWN_MAKES:
            idx = low.find(make.lower())
            if idx >= 0:
                car.make = make
                tail = clean[idx + len(make):].lstrip(" -–—:")
                if mm := re.match(r"([\w\-]{1,24})", tail):
                    car.model = mm.group(1)
                break

        car.fuel = self._match_dict(clean, _FUEL_HINTS) or car.fuel
        car.transmission = self._match_dict(clean, _TRANS_HINTS) or car.transmission
        car.drive = self._match_dict(clean, _DRIVE_HINTS) or car.drive
        car.body = self._match_dict(clean, _BODY_HINTS) or car.body

        for color in _COLOR_HINTS:
            if color in low:
                car.color = color
                break

        for canonical, needles in _GE_CITIES:
            if any(n in low for n in needles):
                car.city = canonical
                break

        if not (car.make or car.year or car.price):
            return None

        first_line = clean.splitlines()[0].strip()
        car.summary = first_line[:80]
        car.description = clean
        return car


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
        '  "model":        string|null,   // model designation as written, e.g. "Camry", "X5", "E 350"\n'
        '  "year":         integer|null,  // model/production year, 1980..2031\n'
        '  "fuel":         "Бензин"|"Дизель"|"Гибрид"|"Электро"|"Газ"|null,\n'
        '  "engine":       number|null,   // displacement in liters, e.g. 2.0\n'
        '  "power":        integer|null,  // horsepower (л.с.)\n'
        '  "mileage":      integer|null,  // odometer in kilometers; convert from miles if needed\n'
        '  "transmission": "Механика"|"Автомат"|"Робот"|"Вариатор"|null,\n'
        '  "drive":        "Передний"|"Задний"|"Полный"|null,\n'
        '  "body":         "Седан"|"Хэтчбек"|"Универсал"|"Кроссовер"|"Внедорожник"|"Купе"|"Минивэн"|"Пикап"|null,\n'
        '  "color":        string|null,   // colour in Russian, lowercase, e.g. "белый"\n'
        '  "city":         "Тбилиси"|"Батуми"|"Кутаиси"|"Рустави"|"Гори"|"Зугдиди"|"Поти"|"Телави"|null,\n'
        '  "price":        integer|null,  // price in USD; convert if posted in GEL (≈0.37 USD) or EUR (≈1.05 USD); ignore monthly-installment numbers\n'
        '  "summary":      string|null,   // ≤80 chars, Russian, suitable as a card title (e.g. "Toyota Camry 2019, 2.5л, автомат")\n'
        '  "description":  string|null,   // post body cleaned of phone numbers, @usernames, URLs, emoji, and markup\n'
        '  "features":     string[]       // short Russian feature tags, e.g. ["панорама","кожа","камера 360","адаптивный круиз"]\n'
        "}\n\n"
        "RULES:\n"
        "- If the post advertises multiple cars, parse only the FIRST.\n"
        "- If the post is not a car-for-sale ad, return {\"is_listing\": false} and null/empty for all other fields.\n"
        "- Never invent data. If something isn't stated, the value is null.\n"
        "- Strip all phone numbers, @usernames, t.me/wa.me/viber links, and emoji from `description`.\n"
        "- Output VALID JSON only."
    )

    def __init__(self, base_url: str | None = None, model: str | None = None) -> None:
        self.base_url = (base_url or settings.QWEN_BASE_URL).rstrip("/")
        self.model = model or settings.QWEN_MODEL

    async def parse(self, text: str) -> ParsedCar | None:
        if not text or not text.strip():
            return None
        timeout = aiohttp.ClientTimeout(total=120)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(
                f"{self.base_url}/chat/completions",
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": self.SYSTEM_PROMPT},
                        {"role": "user", "content": text.strip()},
                    ],
                    "temperature": 0,
                    "response_format": {"type": "json_object"},
                },
            ) as resp:
                resp.raise_for_status()
                payload = await resp.json()
        content = payload["choices"][0]["message"]["content"]
        data = json.loads(content)
        if data.get("is_listing") is False:
            return None
        scrubbed = {k: v for k, v in data.items() if v is not None}
        return ParsedCar(**scrubbed)
