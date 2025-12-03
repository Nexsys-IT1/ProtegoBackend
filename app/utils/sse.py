import asyncio
import json
from fastapi.responses import StreamingResponse


async def sse_parallel(functions: list):

    async def event_stream():
        queue = asyncio.Queue()

        # worker that calls each function
        async def worker(item):
            name = item["name"]
            func = item["func"]

            try:
                response = await func()
                await queue.put({"api": name, "response": response})
            except Exception as e:
                await queue.put({"api": name, "error": str(e)})

        # producer: runs all workers in parallel
        async def producer():
            tasks = [asyncio.create_task(worker(fn)) for fn in functions]
            await asyncio.gather(*tasks)
            await queue.put(None)  # signal completion

        asyncio.create_task(producer())

        # yield queue results as SSE messages
        while True:
            item = await queue.get()
            if item is None:
                break
            yield f"data: {json.dumps(item)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
