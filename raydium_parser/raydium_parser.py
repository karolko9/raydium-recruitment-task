from collections.abc import Iterator
from dataclasses import dataclass
from typing import Literal

from solders.transaction_status import UiConfirmedBlock


@dataclass
class RaydiumSwap:
    slot: int
    index_in_slot: int
    index_in_tx: int

    signature: str

    was_successful: bool

    mint_in: int
    mint_out: int
    amount_in: int
    amount_out: int

    limit_amount: int
    limit_side: Literal["mint_in", "mint_out"]

    post_pool_balance_mint_in: int
    post_pool_balance_mint_out: int


def parse_block(block: UiConfirmedBlock, slot: int) -> Iterator[RaydiumSwap]:  # noqa: ARG001
    # TODO implement parsing logic here

    for _ in range(10):
        yield RaydiumSwap(
            slot=slot,
            index_in_slot=0,
            index_in_tx=0,
            signature="signature",
            was_successful=True,
            mint_in=123456789,
            mint_out=987654321,
            amount_in=1000000,
            amount_out=2000000,
            limit_amount=5000000,
            limit_side="mint_in",
            post_pool_balance_mint_in=123456789,
            post_pool_balance_mint_out=987654321,
        )
