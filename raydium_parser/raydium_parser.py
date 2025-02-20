from collections.abc import Iterator
from dataclasses import dataclass
from typing import Literal

import base58
from solders.transaction_status import UiConfirmedBlock

# Stałe
RAYDIUM_AMM_V4 = "675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8"
SWAP_IN_INSTRUCTION_DISCRIMINATOR = 9
SWAP_OUT_INSTRUCTION_DISCRIMINATOR = 11
SOL_MINT = "So11111111111111111111111111111111111111112"

# Definicja klasy RaydiumSwap
@dataclass
class RaydiumSwap:
    slot: int
    index_in_slot: int
    index_in_tx: int
    signature: str
    was_successful: bool
    mint_in: str
    mint_out: str
    amount_in: int
    amount_out: int
    limit_amount: int
    limit_side: Literal["mint_in", "mint_out"]
    post_pool_balance_mint_in: int
    post_pool_balance_mint_out: int

# Funkcje pomocnicze
def get_account_keys(tx, meta):
    """Zwraca listę kluczy kont, w tym z Address Lookup Tables."""
    account_keys = [str(key) for key in tx.message.account_keys]
    if meta.loaded_addresses:
        alt_accounts = [*meta.loaded_addresses.writable, *meta.loaded_addresses.readonly]
        account_keys += [str(addr) for addr in alt_accounts]
    return account_keys

def get_instructions(tx, meta):
    """Zwraca wszystkie instrukcje transakcji, w tym wewnętrzne."""
    instructions = list(tx.message.instructions)
    if meta.inner_instructions:
        for inner_instr in meta.inner_instructions:
            instructions.extend(inner_instr.instructions)
    return instructions

def get_balance_diff(account_index, pre_balances, post_balances):
    """Oblicza różnicę bilansów tokenów dla danego indeksu konta."""
    if account_index in post_balances and account_index in pre_balances:
        return post_balances[account_index] - pre_balances[account_index]
    return None

def get_mint(vault_index, meta, account_keys):
    """Pobiera adres mint dla danego indeksu skarbca."""
    for balance in meta.post_token_balances:
        if balance.account_index == vault_index:
            return str(balance.mint)
    vault_pubkey = account_keys[vault_index]
    if vault_pubkey == SOL_MINT:
        return SOL_MINT
    return None

def get_pool_balance(vault_index, meta):
    """Pobiera końcowy balans puli dla danego indeksu skarbca."""
    for balance in meta.post_token_balances:
        if balance.account_index == vault_index:
            return int(balance.ui_token_amount.amount)
    return None

def get_pool_account_indices(instruction):
    """Określa indeksy puli bazowej i kwotowej na podstawie instrukcji."""
    accounts = instruction.accounts
    account_length = len(accounts)
    if account_length == 17:
        return accounts[4], accounts[5]
    elif account_length == 18:
        return accounts[5], accounts[6]
    else:
        raise ValueError(f"Invalid number of accounts: {account_length}")

def parse_swap_instruction(data):
    """Parsuje dane instrukcji swapu i zwraca szczegóły."""
    discriminator = data[0]
    if discriminator == SWAP_IN_INSTRUCTION_DISCRIMINATOR:
        amount_in_instruction = int.from_bytes(data[1:9], "little")
        limit_amount = int.from_bytes(data[9:17], "little")  # min_amount_out
        return True, amount_in_instruction, limit_amount, None, "mint_out"
    elif discriminator == SWAP_OUT_INSTRUCTION_DISCRIMINATOR:
        limit_amount = int.from_bytes(data[1:9], "little")  # max_amount_in
        amount_out_instruction = int.from_bytes(data[9:17], "little")
        return False, None, limit_amount, amount_out_instruction, "mint_in"
    else:
        raise ValueError(f"Invalid instruction discriminator: {discriminator}")

def parse_block(block: UiConfirmedBlock, slot: int) -> Iterator[RaydiumSwap]:
    """Parsuje blok w poszukiwaniu swapów Raydium i zwraca ich szczegóły."""
    if block.transactions is None:
        return

    # Inicjalizacja liczników błędów
    total_swaps = 0
    successful_swaps = 0
    errors_amount_x_in_swap_is_not_sync_with_instruction = 0
    limit_not_respected = 0
    swaps_with_same_mint = 0
    amount_in_out_errors = 0

    for tx_idx, tx_with_status in enumerate(block.transactions):
        tx = tx_with_status.transaction
        meta = tx_with_status.meta
        if not meta or not tx.signatures:
            continue

        account_keys = get_account_keys(tx, meta)
        try:
            raydium_program_idx = account_keys.index(RAYDIUM_AMM_V4)
        except ValueError:
            continue

        signature = str(tx.signatures[0])
        instructions = get_instructions(tx, meta)

        # Przygotowanie bilansów dla szybszego dostępu
        pre_balances = {b.account_index: int(b.ui_token_amount.amount) for b in meta.pre_token_balances}
        post_balances = {b.account_index: int(b.ui_token_amount.amount) for b in meta.post_token_balances}

        for instr_idx, instr in enumerate(instructions):
            if instr.program_id_index != raydium_program_idx:
                continue

            try:
                data = base58.b58decode(instr.data)
                if len(data) < 17 or data[0] not in (SWAP_IN_INSTRUCTION_DISCRIMINATOR, SWAP_OUT_INSTRUCTION_DISCRIMINATOR):
                    continue
            except Exception as e:
                print(f"[INSTR {tx_idx}.{instr_idx}] Error decoding instruction data: {str(e)}")
                continue

            total_swaps += 1
            was_successful = meta.err is None
            if was_successful:
                successful_swaps += 1

            # Parsowanie instrukcji swapu
            try:
                is_swap_base_in, amount_in_instruction, limit_amount, amount_out_instruction, limit_side = parse_swap_instruction(data)
            except ValueError as e:
                print(f"[INSTR {tx_idx}.{instr_idx}] {str(e)}")
                return

            # Określenie indeksów puli
            try:
                pool_base_idx, pool_quote_idx = get_pool_account_indices(instr)
            except ValueError as e:
                print(f"[INSTR {tx_idx}.{instr_idx}] {str(e)}")
                return

            # Pobranie mintów
            mint_base = get_mint(pool_base_idx, meta, account_keys)
            mint_quote = get_mint(pool_quote_idx, meta, account_keys)
            if mint_base is None or mint_quote is None:
                print(f"[INSTR {tx_idx}.{instr_idx}] Unknown mint for pool_base_idx: {pool_base_idx} or pool_quote_idx: {pool_quote_idx}")
                return

            # Obliczenie różnic bilansów
            diff_base = get_balance_diff(pool_base_idx, pre_balances, post_balances)
            diff_quote = get_balance_diff(pool_quote_idx, pre_balances, post_balances)
            if diff_base is None or diff_quote is None:
                print(f"[INSTR {tx_idx}.{instr_idx}] Failed to retrieve amount_in or amount_out")
                amount_in_out_errors += was_successful
                continue

            # Określenie kierunku swapu
            if diff_base > 0 and diff_quote < 0:
                mint_in, mint_out = mint_base, mint_quote
                pool_in_idx, pool_out_idx = pool_base_idx, pool_quote_idx
                amount_in, amount_out = abs(diff_base), abs(diff_quote)
            elif diff_base < 0 and diff_quote > 0:
                mint_in, mint_out = mint_quote, mint_base
                pool_in_idx, pool_out_idx = pool_quote_idx, pool_base_idx
                amount_in, amount_out = abs(diff_quote), abs(diff_base)
            else:
                print(f"[INSTR {tx_idx}.{instr_idx}] Invalid balance changes")
                amount_in_out_errors += was_successful
                continue

            # Pobranie końcowych bilansów puli
            post_pool_in = get_pool_balance(pool_in_idx, meta)
            post_pool_out = get_pool_balance(pool_out_idx, meta)
            if post_pool_in is None or post_pool_out is None:
                print(f"[INSTR {tx_idx}.{instr_idx}] Failed to retrieve post pool balances")
                amount_in_out_errors += was_successful
                continue

            # Sprawdzenie błędów
            if mint_in == mint_out:
                swaps_with_same_mint += was_successful

            # Tworzenie obiektu swapu
            swap = RaydiumSwap(
                slot=slot,
                index_in_slot=tx_idx,
                index_in_tx=instr_idx,
                signature=signature,
                was_successful=was_successful,
                mint_in=mint_in,
                mint_out=mint_out,
                amount_in=amount_in,
                amount_out=amount_out,
                limit_amount=limit_amount,
                limit_side=limit_side,
                post_pool_balance_mint_in=post_pool_in,
                post_pool_balance_mint_out=post_pool_out,
            )

            # Debugowanie szczegółów swapu
            print("================================================")
            print(f"signature: {swap.signature}")
            print(f"was_successful: {swap.was_successful}")
            print(f"mint_in: {swap.mint_in}")
            print(f"mint_out: {swap.mint_out}")
            print(f"amount_in: {swap.amount_in}")
            print(f"amount_out: {swap.amount_out}")
            print(f"limit_amount: {swap.limit_amount}")
            print(f"limit_side: {swap.limit_side}")
            print(f"post_pool_balance_mint_in: {swap.post_pool_balance_mint_in}")
            print(f"post_pool_balance_mint_out: {swap.post_pool_balance_mint_out}")
            print("--------------------------------")

            if is_swap_base_in:
                print(f"[INSTR {tx_idx}.{instr_idx}] amount_in_instruction: {amount_in_instruction}")
                print(f"[INSTR {tx_idx}.{instr_idx}] amount_in: {amount_in}")
                print(f"[INSTR {tx_idx}.{instr_idx}] amount_in == amount_in_instruction: {amount_in == amount_in_instruction}")
                print(f"[INSTR {tx_idx}.{instr_idx}] limit_respected: {was_successful and amount_out >= limit_amount}")
                errors_amount_x_in_swap_is_not_sync_with_instruction += (amount_in != amount_in_instruction) and was_successful
                if was_successful and amount_out < limit_amount:
                    limit_not_respected += 1
                    print(f"[INSTR {tx_idx}.{instr_idx}] Swap failed: amount_out ({amount_out}) < min_amount_out ({limit_amount})")
            else:
                print(f"[INSTR {tx_idx}.{instr_idx}] amount_out_instruction: {amount_out_instruction}")
                print(f"[INSTR {tx_idx}.{instr_idx}] amount_out: {amount_out}")
                print(f"[INSTR {tx_idx}.{instr_idx}] amount_out == amount_out_instruction: {amount_out == amount_out_instruction}")
                print(f"[INSTR {tx_idx}.{instr_idx}] limit_respected: {was_successful and amount_in <= limit_amount}")
                errors_amount_x_in_swap_is_not_sync_with_instruction += (amount_out != amount_out_instruction) and was_successful
                if was_successful and amount_in > limit_amount:
                    limit_not_respected += 1
                    print(f"[INSTR {tx_idx}.{instr_idx}] Swap failed: amount_in ({amount_in}) > max_amount_in ({limit_amount})")

            print(f"[INSTR {tx_idx}.{instr_idx}] data_instr_discriminator: {data[0]}")
            print("--------------------------------")

            # Debugowanie bilansów
            every_balances_diff = {i: meta.post_balances[i] - meta.pre_balances[i] 
                                 for i in range(len(meta.pre_balances)) 
                                 if meta.post_balances[i] - meta.pre_balances[i] != 0}
            every_token_balances_diff = {}
            if meta.post_token_balances:
                for post_balance in meta.post_token_balances:
                    found_match = False
                    for pre_balance in meta.pre_token_balances:
                        if pre_balance.mint == post_balance.mint:
                            every_token_balances_diff[post_balance.account_index] = (
                                str(pre_balance.mint),
                                int(post_balance.ui_token_amount.amount) - int(pre_balance.ui_token_amount.amount),
                            )
                            found_match = True
                            break
                    if not found_match:
                        every_token_balances_diff[post_balance.account_index] = (
                            str(post_balance.mint),
                            int(post_balance.ui_token_amount.amount),
                        )
            print(f"every_balances_diff: {every_balances_diff}")
            print(f"every_token_balances_diff: {every_token_balances_diff}")
            print("================================================")

            # yield swap  

    # Podsumowanie bloku
    print("\n[BLOK] Podsumowanie:")
    print(f"[BLOK] Znalezionych swapów: {total_swaps}")
    print(f"[BLOK] Udanych swapów: {successful_swaps}")
    print(f"[BLOK] Swapów z tym samym mint adresem gdy jest successful (should be 0): {swaps_with_same_mint}")
    print(f"[BLOK] limit_not_respected when successful (should be 0): {limit_not_respected}")
    print(f"[BLOK] errors_amount_x_in_swap_is_not_sync_with_instruction_when_successful (should be 0): {errors_amount_x_in_swap_is_not_sync_with_instruction}")
    print(f"[BLOK] amount_in_out_errors (pobranie amount_in/out) (should be 0): {amount_in_out_errors}")
