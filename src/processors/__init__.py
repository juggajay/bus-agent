"""Signal processing module."""

from .embeddings import EmbeddingGenerator, get_embedding_generator
from .classifier import SignalClassifier, get_classifier
from .thesis_scorer import ThesisScorer, get_thesis_scorer
from .novelty import (
    calculate_novelty_score,
    find_similar_signals,
    average_embedding,
    cluster_by_embedding,
    cosine_similarity
)
from .velocity import (
    calculate_velocity_score,
    VelocityTracker,
    get_velocity_tracker
)
from .pipeline import ProcessingPipeline, get_pipeline

__all__ = [
    "EmbeddingGenerator", "get_embedding_generator",
    "SignalClassifier", "get_classifier",
    "ThesisScorer", "get_thesis_scorer",
    "calculate_novelty_score", "find_similar_signals",
    "average_embedding", "cluster_by_embedding", "cosine_similarity",
    "calculate_velocity_score", "VelocityTracker", "get_velocity_tracker",
    "ProcessingPipeline", "get_pipeline"
]
