"""Pattern detection module."""

from .convergence import ConvergenceDetector, get_convergence_detector
from .velocity_spike import VelocitySpikeDetector, get_velocity_spike_detector
from .gap_detector import GapDetector, get_gap_detector
from .timing import TimingAnalyzer, get_timing_analyzer
from .detector import PatternDetector, get_pattern_detector

__all__ = [
    "ConvergenceDetector", "get_convergence_detector",
    "VelocitySpikeDetector", "get_velocity_spike_detector",
    "GapDetector", "get_gap_detector",
    "TimingAnalyzer", "get_timing_analyzer",
    "PatternDetector", "get_pattern_detector"
]
