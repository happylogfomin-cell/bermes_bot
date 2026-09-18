import secrets


def generate_crash_point() -> float:
    r = secrets.randbelow(1000) / 1000.0
    if r < 0.5:
        return round(1.0 + r * 2, 2)
    elif r < 0.8:
        return round(2.0 + (r - 0.5) * 10, 2)
    elif r < 0.95:
        return round(5.0 + (r - 0.8) * 33, 2)
    else:
        return round(10.0 + (r - 0.95) * 1800, 2)
