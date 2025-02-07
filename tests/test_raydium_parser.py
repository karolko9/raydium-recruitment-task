from raydium_parser.raydium_parser import parse_block
from raydium_parser.rpc_utils import get_block


def test_raydium_parser():
    block = get_block(316719543)

    swaps = parse_block(block, 316719543)

    first_swap = next(swaps)

    assert first_swap.slot == 316719543
    assert first_swap.index_in_slot == 0
    assert first_swap.index_in_tx == 0
    assert first_swap.signature == "signature"
    assert first_swap.was_successful
    assert first_swap.mint_in == 123456789
    assert first_swap.mint_out == 987654321
    assert first_swap.amount_in == 1000000
    assert first_swap.amount_out == 2000000
    assert first_swap.limit_amount == 5000000
    assert first_swap.limit_side == "mint_in"
    assert first_swap.post_pool_balance_mint_in == 123456789
    assert first_swap.post_pool_balance_mint_out == 987654321
