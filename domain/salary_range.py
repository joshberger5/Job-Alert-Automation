from dataclasses import dataclass


@dataclass(frozen=True)
class SalaryRange:
    minimum: int | None
    maximum: int | None

    @staticmethod
    def from_raw(raw_salary: str | None) -> "SalaryRange":
        if not raw_salary:
            return SalaryRange(None, None)

        cleaned = raw_salary.replace(",", "").replace("$", "")
        parts = cleaned.split()

        numeric_values = []

        for part in parts:
            if part.isdigit():
                numeric_values.append(int(part))

        if not numeric_values:
            return SalaryRange(None, None)

        if len(numeric_values) == 1:
            return SalaryRange(numeric_values[0], numeric_values[0])

        return SalaryRange(min(numeric_values), max(numeric_values))

    def meets_minimum(self, required_minimum: int) -> bool:
        if self.maximum is None:
            return False

        return self.maximum >= required_minimum