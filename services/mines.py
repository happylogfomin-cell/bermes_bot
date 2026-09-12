import secrets

SIZE = 5

def new_field(mines: int) -> set[int]:
    cells = list(range(SIZE * SIZE))
    result = set()
    for _ in range(mines):
        result.add(cells.pop(secrets.randbelow(len(cells))))
    return result

def multiplier(opened: int, mines: int) -> float:
    if opened <= 0:
        return 1.0
    total = SIZE * SIZE
    safe = total - mines
    prob = 1.0
    for i in range(opened):
        prob *= (safe - i) / (total - i)
    return round(0.97 / prob, 2)