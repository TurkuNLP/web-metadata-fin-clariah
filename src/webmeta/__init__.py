"""webmeta: language, country and register metadata for web data.

FIN-CLARIAH deliverable D3.3.3 (a), TurkuNLP, University of Turku.
"""

from .io import from_hplt4, from_mapping, read, write
from .pipeline import annotate, run, select, summary
from .schema import ContractError, check, coverage

__version__ = "0.1.0"
