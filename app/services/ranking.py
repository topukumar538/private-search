def rank_results(results: list[dict]) -> list[dict]:
    scored_results = []

    for result in results:
        score = sum(
            1 / (60 + rank)
            for rank in result["source_ranks"].values()
        )

        scored_results.append({
            **result,
            "score": score,
        })

    return sorted(
        scored_results,
        key=lambda result: (-result["score"], result["url"]),
    )