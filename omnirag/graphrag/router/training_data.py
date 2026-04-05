"""Generate training data for BERT query router classifier.

Produces 10,000 labelled queries: 2,500 per class (BASIC, LOCAL, GLOBAL, DRIFT).
Uses templates + variation for deterministic generation (LLM optional for augmentation).
"""

from __future__ import annotations

import json
import random
from pathlib import Path

BASIC_TEMPLATES = [
    "What is {topic}?", "Define {topic}.", "When did {event} happen?",
    "Who is {person}?", "Where is {place}?", "How many {thing} are there?",
    "What does {term} mean?", "Is {statement} true?", "List {count} types of {topic}.",
    "What year was {thing} created?", "How old is {thing}?",
    "What is the value of {metric}?", "What color is {thing}?",
    "Name the {thing} of {topic}.", "What is {topic} used for?",
]

LOCAL_TEMPLATES = [
    "How is {entity1} related to {entity2}?", "What does {entity1} say about {entity2}?",
    "Details about {entity1}.", "What is the connection between {entity1} and {entity2}?",
    "Show me everything about {entity1}.", "What role does {entity1} play in {entity2}?",
    "What are the properties of {entity1}?", "Compare {entity1} and {entity2}.",
    "How does {entity1} interact with {entity2}?", "What entities are linked to {entity1}?",
    "Trace the relationship from {entity1} to {entity2}.",
    "What documents mention {entity1}?", "Show the graph around {entity1}.",
]

GLOBAL_TEMPLATES = [
    "Summarize all themes in the corpus.", "What are the main topics across all documents?",
    "List all risks mentioned.", "Overview of the entire dataset.",
    "What trends appear across the documents?", "High-level summary of everything.",
    "What are the most common themes?", "Summarize the key findings.",
    "What patterns emerge across the corpus?", "List all themes and topics.",
    "What does the corpus say overall?", "Broad summary of all content.",
    "What are the top-level categories?", "Overview of risks and opportunities.",
]

DRIFT_TEMPLATES = [
    "Investigate how {entity1} connects to {entity2}.",
    "Connect the dots between {entity1} and {entity2}.",
    "Explore the relationship between {topic1} and {topic2}.",
    "Hypothesize why {entity1} is linked to {entity2}.",
    "Trace the chain from {entity1} through the graph to {entity2}.",
    "Investigate whether {statement}.",
    "Explore how {topic1} evolved across documents.",
    "What deeper connections exist between {entity1} and {entity2}?",
    "Investigate the broader context around {entity1}.",
    "How did {entity1} influence {entity2} across the corpus?",
]

ENTITIES = ["OmniRAG", "Neo4j", "PostgreSQL", "Python", "Qdrant", "Elasticsearch",
            "Microsoft", "Google", "Amazon", "RAG", "GraphRAG", "LangChain",
            "OpenAI", "Anthropic", "Docker", "Kubernetes", "Redis", "FastAPI",
            "Terraform", "GDPR", "HIPAA", "SOC2", "ISO27001", "PCI-DSS"]

TOPICS = ["machine learning", "natural language processing", "data governance",
          "compliance", "cybersecurity", "cloud architecture", "microservices",
          "vector databases", "knowledge graphs", "retrieval-augmented generation"]

EVENTS = ["the data breach", "the migration", "the acquisition", "the release",
          "the incident", "the audit", "the deployment", "the outage"]

PERSONS = ["the CEO", "the CTO", "the architect", "the engineer", "the auditor"]


def _fill(template: str) -> str:
    """Fill template slots with random values."""
    result = template
    for key, pool in [
        ("{entity1}", ENTITIES), ("{entity2}", ENTITIES),
        ("{topic}", TOPICS), ("{topic1}", TOPICS), ("{topic2}", TOPICS),
        ("{event}", EVENTS), ("{person}", PERSONS), ("{place}", ENTITIES),
        ("{thing}", ENTITIES + TOPICS), ("{term}", TOPICS),
        ("{statement}", ["the system is compliant", "there are security risks"]),
        ("{count}", ["3", "5", "10"]), ("{metric}", ["latency", "throughput", "accuracy"]),
    ]:
        if key in result:
            result = result.replace(key, random.choice(pool), 1)
    return result


def generate_training_data(output_path: str | None = None, count_per_class: int = 2500) -> list[dict]:
    """Generate labelled queries for router training.

    Returns list of {"text": "...", "label": 0-3}.
    Labels: 0=BASIC, 1=LOCAL, 2=GLOBAL, 3=DRIFT
    """
    data = []
    templates_map = {
        0: BASIC_TEMPLATES,
        1: LOCAL_TEMPLATES,
        2: GLOBAL_TEMPLATES,
        3: DRIFT_TEMPLATES,
    }

    for label, templates in templates_map.items():
        for i in range(count_per_class):
            template = random.choice(templates)
            text = _fill(template)
            # Add some variation
            if random.random() < 0.3:
                text = text.lower()
            if random.random() < 0.2:
                text = text.rstrip("?.!") + "?"
            data.append({"text": text, "label": label})

    random.shuffle(data)

    if output_path:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            for item in data:
                f.write(json.dumps(item) + "\n")

    return data


def load_training_data(path: str) -> list[dict]:
    """Load JSONL training data."""
    data = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                data.append(json.loads(line))
    return data
