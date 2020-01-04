async def test():
    return 1

print(hasattr(test(), '__anext__'))