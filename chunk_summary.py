MAX_CHARS = 2000

with open("summary.md", "r", encoding="utf-8", newline="") as f:
    lines = f.readlines()

chunks = []
current = ""

for line in lines:
    if current and len(current) + len(line) > MAX_CHARS:
        chunks.append(current)
        current = ""
    current += line

if current:
    chunks.append(current)

for n, chunk in enumerate(chunks, start=1):
    with open(f"summary_chunk_{n}.md", "w", encoding="utf-8", newline="") as f:
        f.write(chunk)

print(f"Wrote {len(chunks)} chunks")
