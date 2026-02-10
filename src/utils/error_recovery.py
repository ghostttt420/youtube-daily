"""Error recovery and checkpoint management."""

from __future__ import annotations

import pickle
import shutil
import traceback
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import structlog

from src.config import get_settings

logger = structlog.get_logger()


class SimulationCrash(Exception):
    """Custom exception for simulation crashes."""
    pass


@dataclass
class CrashReport:
    """Report of a simulation crash."""
    generation: int
    timestamp: str
    exception_type: str
    exception_message: str
    traceback: str
    checkpoint_path: str | None
    recovery_successful: bool = False


class ErrorRecovery:
    """Handles error recovery and emergency checkpoints."""

    def __init__(self) -> None:
        """Initialize error recovery."""
        self.settings = get_settings()
        self.crash_log_dir = self.settings.paths.data_dir / "crashes"
        self.emergency_dir = self.settings.paths.data_dir / "emergency"
        self.recovery_attempts = 0
        self.max_recovery_attempts = 3
        
        self.crash_log_dir.mkdir(parents=True, exist_ok=True)
        self.emergency_dir.mkdir(parents=True, exist_ok=True)

    def with_recovery(self, func, *args, **kwargs) -> Any:
        """Execute function with error recovery."""
        try:
            return func(*args, **kwargs)
        except Exception as e:
            return self._handle_crash(e, func.__name__)

    def _handle_crash(self, exception: Exception, context: str) -> Any:
        """Handle a crash and attempt recovery."""
        self.recovery_attempts += 1
        
        crash_report = CrashReport(
            generation=getattr(self, "current_generation", 0),
            timestamp=datetime.now().isoformat(),
            exception_type=type(exception).__name__,
            exception_message=str(exception),
            traceback=traceback.format_exc(),
            checkpoint_path=None,
        )
        
        logger.error(
            "simulation_crashed",
            context=context,
            exception=crash_report.exception_type,
            message=crash_report.exception_message,
            attempt=self.recovery_attempts,
        )
        
        # Save crash report
        self._save_crash_report(crash_report)
        
        # Try to save emergency checkpoint
        try:
            emergency_path = self._save_emergency_checkpoint()
            crash_report.checkpoint_path = str(emergency_path)
        except Exception as e:
            logger.error("emergency_checkpoint_failed", error=str(e))
        
        # Attempt recovery if under max attempts
        if self.recovery_attempts < self.max_recovery_attempts:
            logger.info("attempting_recovery", attempt=self.recovery_attempts)
            
            # Try to restore from latest checkpoint
            restored = self._restore_from_checkpoint()
            if restored:
                crash_report.recovery_successful = True
                self._update_crash_report(crash_report)
                logger.info("recovery_successful")
                return restored
        
        # Max attempts reached or recovery failed
        logger.error("recovery_failed_max_attempts", attempts=self.recovery_attempts)
        raise SimulationCrash(
            f"Simulation crashed after {self.recovery_attempts} recovery attempts: {exception}"
        ) from exception

    def _save_crash_report(self, report: CrashReport) -> Path:
        """Save crash report to file."""
        filename = f"crash_gen{report.generation}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        path = self.crash_log_dir / filename
        
        with open(path, "w") as f:
            f.write(f"Crash Report - Generation {report.generation}\n")
            f.write(f"Timestamp: {report.timestamp}\n")
            f.write(f"Exception: {report.exception_type}\n")
            f.write(f"Message: {report.exception_message}\n")
            f.write(f"\nTraceback:\n{report.traceback}\n")
            if report.checkpoint_path:
                f.write(f"\nEmergency checkpoint: {report.checkpoint_path}\n")
        
        return path

    def _update_crash_report(self, report: CrashReport) -> None:
        """Update crash report with recovery status."""
        # Find the latest crash report for this generation
        pattern = f"crash_gen{report.generation}_*.txt"
        reports = sorted(self.crash_log_dir.glob(pattern))
        
        if reports:
            with open(reports[-1], "a") as f:
                f.write(f"\nRecovery: {'SUCCESSFUL' if report.recovery_successful else 'FAILED'}\n")

    def _save_emergency_checkpoint(self) -> Path:
        """Save emergency checkpoint of current state."""
        # Find latest neat checkpoint
        checkpoints = sorted(Path(".").glob("neat-checkpoint-*"))
        
        if checkpoints:
            latest = checkpoints[-1]
            emergency_path = self.emergency_dir / f"emergency_{latest.name}"
            shutil.copy(latest, emergency_path)
            logger.info("emergency_checkpoint_saved", path=str(emergency_path))
            return emergency_path
        
        raise RuntimeError("No checkpoint available for emergency save")

    def _restore_from_checkpoint(self) -> Any:
        """Attempt to restore from most recent valid checkpoint."""
        import neat
        
        # Try checkpoints in order of recency
        checkpoints = sorted(Path(".").glob("neat-checkpoint-*"), reverse=True)
        
        for checkpoint in checkpoints:
            try:
                population = neat.Checkpointer.restore_checkpoint(str(checkpoint))
                logger.info("restored_from_checkpoint", path=str(checkpoint))
                return population
            except (pickle.PickleError, EOFError, Exception) as e:
                logger.warning("checkpoint_restore_failed", path=str(checkpoint), error=str(e))
                continue
        
        # Try emergency checkpoints
        emergency = sorted(self.emergency_dir.glob("emergency_*"), reverse=True)
        for checkpoint in emergency:
            try:
                population = neat.Checkpointer.restore_checkpoint(str(checkpoint))
                logger.info("restored_from_emergency", path=str(checkpoint))
                return population
            except Exception as e:
                logger.warning("emergency_restore_failed", path=str(checkpoint), error=str(e))
                continue
        
        return None

    def reset_recovery_count(self) -> None:
        """Reset recovery attempt counter (call after successful generation)."""
        self.recovery_attempts = 0

    def get_recovery_stats(self) -> dict:
        """Get recovery statistics."""
        crash_reports = list(self.crash_log_dir.glob("crash_*.txt"))
        emergency_checkpoints = list(self.emergency_dir.glob("emergency_*"))
        
        return {
            "total_crashes": len(crash_reports),
            "emergency_checkpoints": len(emergency_checkpoints),
            "recovery_attempts": self.recovery_attempts,
            "max_attempts": self.max_recovery_attempts,
        }
