import copy
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional
from config import Config

logger = logging.getLogger(__name__)

# Server-side cache of loaded cases (includes truth_sheet and contradictions)
_CASES: Dict[str, dict] = {}

def load_all_cases(cases_dir: Optional[Path] = None) -> Dict[str, dict]:
    """Load and validate all JSON cases from the cases directory."""
    global _CASES
    target_dir = cases_dir or Config.CASES_DIR
    target_dir = Path(target_dir)
    
    if not target_dir.exists():
        logger.warning(f"Cases directory not found: {target_dir}")
        return {}

    loaded = {}
    for case_file in sorted(target_dir.glob("*.json")):
        try:
            with open(case_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            case_id = data.get("id")
            if not case_id:
                logger.error(f"Missing 'id' in case file {case_file.name}")
                continue
            
            # Validate required top-level keys
            required_keys = ["id", "title", "blurb", "setting", "briefing", "suspect", "truth_sheet", "cover_story", "evidence", "contradictions"]
            missing = [k for k in required_keys if k not in data]
            if missing:
                logger.error(f"Case {case_file.name} missing required fields: {missing}")
                continue
                
            loaded[case_id] = data
            logger.info(f"Loaded case '{case_id}': {data.get('title')}")
        except Exception as e:
            logger.error(f"Error parsing case file {case_file.name}: {e}")

    _CASES = loaded
    return _CASES

def get_case(case_id: str) -> Optional[dict]:
    """Retrieve full server-side case data (includes truth sheet)."""
    if not _CASES:
        load_all_cases()
    return _CASES.get(case_id)

def sanitize_case_for_client(case_data: dict) -> dict:
    """
    Produce a client-safe case dictionary.
    CRITICAL: Strips truth_sheet and contradictions entirely.
    """
    safe = copy.deepcopy(case_data)
    safe.pop("truth_sheet", None)
    safe.pop("contradictions", None)
    return safe

def list_cases_safe() -> List[dict]:
    """List all available cases in safe client format."""
    if not _CASES:
        load_all_cases()
    return [sanitize_case_for_client(case) for case in _CASES.values()]
