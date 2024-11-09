import asyncio
import aiohttp
import random
from time import time

BASE_URL = "http://localhost:8000/api/generate"
REQUESTS_PER_SECOND = 5 # A worker can handle about 42 requests per second on average
TOTAL_DURATION = 60  # seconds

async def send_request(session, semaphore):
    async with semaphore:
        width = random.randint(100, 600)
        height = random.randint(100, 600)
        url = f"{BASE_URL}?data=123456789012&width={width}&height={height}"

        list_of_formats = ["code128"]
        format = random.choice(list_of_formats)
        url += f"&format={format}"

        try:
            async with session.get(url) as response:
                await response.read()
                return response.status
        except aiohttp.ClientError as e:
            print(f"Request failed: {e}")
            return None

async def main():
    semaphore = asyncio.Semaphore(REQUESTS_PER_SECOND)
    async with aiohttp.ClientSession() as session:
        start_time = time()
        tasks = []
        request_count = 0

        while time() - start_time < TOTAL_DURATION:
            for _ in range(REQUESTS_PER_SECOND):
                task = asyncio.create_task(send_request(session, semaphore))
                tasks.append(task)
                request_count += 1

            await asyncio.sleep(1)  # Wait for 1 second before sending the next batch

        results = await asyncio.gather(*tasks)

    end_time = time()
    total_time = end_time - start_time
    successful_requests = sum(1 for status in results if status == 200)

    print(f"Total requests sent: {request_count}")
    print(f"Successful requests: {successful_requests}")
    print(f"Failed requests: {request_count - successful_requests}")
    print(f"Total time: {total_time:.2f} seconds")
    print(f"Requests per second: {request_count / total_time:.2f}")

if __name__ == "__main__":
    asyncio.run(main())