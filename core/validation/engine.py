import re
from datetime import datetime
from decimal import Decimal, InvalidOperation

from plugins.base.interfaces import ExtractionCandidate


class ValidationEngine:
    def validate(
        self, candidate: ExtractionCandidate, validators: list[dict[str, object]]
    ) -> tuple[bool, object, str | None]:
        value: object = candidate.value
        for config in validators:
            kind = str(config["type"])
            try:
                value = self._apply(kind, value, config)
            except (ValueError, InvalidOperation) as exc:
                return False, value, str(exc)
        return True, value, None

    def _apply(self, kind: str, value: object, config: dict[str, object]) -> object:
        text = str(value).strip()
        if kind == "not_empty" and not text:
            raise ValueError("Value is empty")
        if kind == "required_pattern" and not re.fullmatch(str(config["pattern"]), text):
            raise ValueError("Value does not match the required pattern")
        if kind == "date":
            configured_formats = config.get("formats", ["%d.%m.%Y", "%Y-%m-%d"])
            formats = (
                configured_formats
                if isinstance(configured_formats, list)
                else ["%d.%m.%Y", "%Y-%m-%d"]
            )
            for date_format in formats:
                try:
                    return datetime.strptime(text, str(date_format)).date().isoformat()
                except ValueError:
                    continue
            raise ValueError("Value is not a supported date")
        if kind == "monetary_amount":
            normalized = re.sub(r"[^\d,.-]", "", text)
            if "," in normalized and "." in normalized:
                decimal_separator = "," if normalized.rfind(",") > normalized.rfind(".") else "."
                thousands_separator = "." if decimal_separator == "," else ","
                normalized = normalized.replace(thousands_separator, "").replace(
                    decimal_separator, "."
                )
            elif "," in normalized:
                normalized = normalized.replace(".", "").replace(",", ".")
            return str(Decimal(normalized).quantize(Decimal("0.01")))
        if kind == "iban":
            compact = re.sub(r"\s+", "", text).upper()
            rearranged = compact[4:] + compact[:4]
            numeric = "".join(
                str(ord(char) - 55) if char.isalpha() else char for char in rearranged
            )
            if len(compact) < 15 or len(compact) > 34 or int(numeric) % 97 != 1:
                raise ValueError("Value is not a valid IBAN")
            return compact
        configured_values = config.get("values", [])
        allowed_values = configured_values if isinstance(configured_values, list) else []
        if kind == "allowed_values" and value not in allowed_values:
            raise ValueError("Value is not in the allowed set")
        if kind == "length" and (
            len(text) < int(str(config.get("min", 0)))
            or len(text) > int(str(config.get("max", 2**31)))
        ):
            raise ValueError("Value length is outside the allowed range")
        if kind == "numeric_range":
            number = Decimal(text.replace(",", "."))
            if "min" in config and number < Decimal(str(config["min"])):
                raise ValueError("Value is below the minimum")
            if "max" in config and number > Decimal(str(config["max"])):
                raise ValueError("Value is above the maximum")
            return str(number)
        return value
