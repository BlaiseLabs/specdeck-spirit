"""The spirit layer: each reason in a project's spec, read next to a spiritual text the person chooses.

A rule in requirements.yaml has a statement and a rationale, the why. This layer takes those whys and the
project's purpose, looks through a text from the person's own tradition with open models running locally,
and proposes the passage that speaks to each one, what it says about it, and further reading. The passages
come out of the fetched text word for word, never out of the model, and the person keeps or rejects them.

    texts.py     the catalogue, fetching, and turning each text into numbered passages
    model.py     Gemma and EmbeddingGemma through Ollama
    retrieve.py  finding candidate passages: BM25, plus embeddings
    align.py     choosing a passage for each why, further reading, the ledger in spirit.yaml
    report.py    SPIRIT.md
    cli.py       `specdeck spirit ...`
"""
