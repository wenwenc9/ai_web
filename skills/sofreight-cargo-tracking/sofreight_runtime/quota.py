from dataclasses import dataclass


CARGO_TRACK_TYPE = 3
PORT_CONGESTION_TYPE = 14  # A001：港口塞港AI智析


@dataclass(frozen=True)
class QuotaSnapshot:
    left_number: int
    coins_num: int
    coins_disabled: bool

    def uses_coins_for(self, needed: int) -> bool:
        return (
            needed > self.left_number
            and not self.coins_disabled
            and self.coins_num > 0
        )


def parse_quota(data: dict, function_type: int) -> QuotaSnapshot:
    left_number = 0
    for item in data.get("use_number", []):
        if int(item["type"]) == function_type:
            left_number = int(item["left_number"])
            break

    coins = data.get("coins", {})
    return QuotaSnapshot(
        left_number=left_number,
        coins_num=int(coins.get("coins_num", 0)),
        coins_disabled=int(coins.get("coins_disable", 0)) == 1,
    )


def can_cover(snapshot: QuotaSnapshot, needed: int) -> bool:
    return needed <= snapshot.left_number or snapshot.uses_coins_for(needed)
