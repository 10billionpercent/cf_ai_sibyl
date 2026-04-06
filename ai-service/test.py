import httpx
import asyncio

INPUT_FILE = "companies.txt"
OUTPUT_FILE = "valid_companies.txt"

CONCURRENCY = 20 # 🔥 speed control


async def check_url(client, line):
    try:
        parts = line.strip().split("|")
        url = parts[-1].strip()

        r = await client.head(url, timeout=10, follow_redirects=True)

        if r.status_code < 400:
            print(f"✅ {url}")
            return line.strip()
        else:
            print(f"❌ {url} ({r.status_code})")
            return None

    except Exception as e:
        print(f"⚠️ {url} ERROR")
        return None


async def main():
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        lines = f.readlines()

    sem = asyncio.Semaphore(CONCURRENCY)

    async with httpx.AsyncClient() as client:

        async def sem_task(line):
            async with sem:
                return await check_url(client, line)

        tasks = [sem_task(line) for line in lines]
        results = await asyncio.gather(*tasks)

    valid = [r for r in results if r]

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        for line in valid:
            f.write(line + "\n")

    print(f"\n🔥 VALID: {len(valid)} / {len(lines)}")


if __name__ == "__main__":
    asyncio.run(main())
