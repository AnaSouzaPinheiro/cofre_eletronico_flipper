from dataclasses import dataclass
from typing import Optional, Tuple


@dataclass(frozen=True)
class Criterion:
    """Define exatamente o que conta como autenticação válida."""
    apdu: Optional[bytes] = None
    expected_data: Optional[bytes] = None
    expected_sw: Tuple[int, int] = (0x90, 0x00)
    expected_atr: Optional[bytes] = None

    @property
    def is_configured(self) -> bool:
        return self.expected_atr is not None or (
            self.apdu is not None and self.expected_data is not None
        )
