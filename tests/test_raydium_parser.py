from raydium_parser.raydium_parser import parse_block
from raydium_parser.rpc_utils import get_block


def test_raydium_parser():
    slot = 316719543
    # slot = 316719546
    block = get_block(slot)

    swaps = parse_block(block, slot)

    first_swap = next(swaps)

    assert 1 == 0
    # TODO: implement tests
