"""Tests for the execution engine."""

from research_lab.engine.base import KernelBackend
from research_lab.engine.jupyter import JupyterKernel
from research_lab.engine.session import SessionManager


def test_kernel_backend_protocol():
    """JupyterKernel should satisfy the KernelBackend protocol."""
    assert isinstance(JupyterKernel(), KernelBackend)


def test_session_manager_init():
    """SessionManager should initialize with no kernels."""
    sm = SessionManager()
    assert sm.kernel_count == 0
    assert sm.active_experiments() == []
