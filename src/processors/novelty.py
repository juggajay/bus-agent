"""Novelty detection for signals."""

from typing import List, Optional
import numpy as np

from ..utils import get_logger

logger = get_logger(__name__)


def cosine_similarity(a: List[float], b: List[float]) -> float:
    """Calculate cosine similarity between two vectors."""
    a_arr = np.array(a)
    b_arr = np.array(b)

    dot_product = np.dot(a_arr, b_arr)
    norm_a = np.linalg.norm(a_arr)
    norm_b = np.linalg.norm(b_arr)

    if norm_a == 0 or norm_b == 0:
        return 0.0

    return dot_product / (norm_a * norm_b)


def calculate_novelty_score(
    new_embedding: List[float],
    recent_embeddings: List[List[float]],
    threshold: float = 0.85
) -> float:
    """
    Calculate novelty score for a new signal.

    Args:
        new_embedding: Embedding vector for the new signal
        recent_embeddings: List of embedding vectors from recent signals
        threshold: Similarity threshold above which signals are considered duplicates

    Returns:
        Novelty score between 0 and 1.
        1 = completely novel (no similar signals)
        0 = duplicate or very similar to existing signal
    """
    if not recent_embeddings:
        return 1.0

    if not new_embedding:
        return 0.5  # Default when no embedding available

    # Calculate similarity to all recent signals
    similarities = [
        cosine_similarity(new_embedding, e)
        for e in recent_embeddings
        if e is not None
    ]

    if not similarities:
        return 1.0

    max_similarity = max(similarities)

    if max_similarity > threshold:
        return 0.0  # Too similar to existing signal

    # Scale remaining range to 0-1
    # Higher max_similarity = lower novelty
    return 1 - (max_similarity / threshold)


def find_similar_signals(
    query_embedding: List[float],
    signal_embeddings: List[List[float]],
    threshold: float = 0.8,
    top_k: int = 10
) -> List[tuple]:
    """
    Find similar signals based on embedding similarity.

    Args:
        query_embedding: Embedding to search for
        signal_embeddings: List of (signal_id, embedding) tuples
        threshold: Minimum similarity threshold
        top_k: Maximum number of results to return

    Returns:
        List of (index, similarity) tuples for matching signals
    """
    if not query_embedding or not signal_embeddings:
        return []

    results = []
    for i, embedding in enumerate(signal_embeddings):
        if embedding is None:
            continue

        similarity = cosine_similarity(query_embedding, embedding)
        if similarity >= threshold:
            results.append((i, similarity))

    # Sort by similarity descending
    results.sort(key=lambda x: x[1], reverse=True)

    return results[:top_k]


def average_embedding(embeddings: List[List[float]]) -> Optional[List[float]]:
    """Calculate the average of multiple embeddings."""
    valid_embeddings = [e for e in embeddings if e is not None]

    if not valid_embeddings:
        return None

    arr = np.array(valid_embeddings)
    return np.mean(arr, axis=0).tolist()


def cluster_by_embedding(
    embeddings: List[List[float]],
    threshold: float = 0.75,
    min_cluster_size: int = 2
) -> List[List[int]]:
    """
    Cluster signals by embedding similarity.

    Simple greedy clustering algorithm:
    1. Start with first unassigned signal
    2. Add all similar signals to cluster
    3. Repeat until all signals assigned

    Args:
        embeddings: List of embedding vectors
        threshold: Similarity threshold for clustering
        min_cluster_size: Minimum size to consider a valid cluster

    Returns:
        List of clusters, where each cluster is a list of indices
    """
    if not embeddings:
        return []

    n = len(embeddings)
    assigned = [False] * n
    clusters = []

    for i in range(n):
        if assigned[i] or embeddings[i] is None:
            continue

        # Start new cluster
        cluster = [i]
        assigned[i] = True

        # Find all similar signals
        for j in range(i + 1, n):
            if assigned[j] or embeddings[j] is None:
                continue

            similarity = cosine_similarity(embeddings[i], embeddings[j])
            if similarity >= threshold:
                cluster.append(j)
                assigned[j] = True

        if len(cluster) >= min_cluster_size:
            clusters.append(cluster)

    return clusters
