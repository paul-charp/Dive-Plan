def frange(start, stop, step):
    while start < stop:
        yield round(start, 10)
        start += step
