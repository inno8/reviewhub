import asyncio
from app.services.diff_extractor import DiffExtractor

async def test():
    extractor = DiffExtractor()
    result = await extractor.extract_commit_diff(
        repo_url='https://github.com/inno8/reviewhub',
        commit_sha='b29e4a7'
    )
    if result:
        print(f"Commit: {result['commit_sha']}")
        print(f"Files changed: {len(result['files'])}")
        print(f"Lines added: {result['lines_added']}")
        print(f"Lines removed: {result['lines_removed']}")
        for f in result['files'][:3]:
            print(f"  - {f['path']} ({f['language']})")
    else:
        print("No result")

asyncio.run(test())
