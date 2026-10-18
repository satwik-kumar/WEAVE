"""Keep dependency error messages out of application logs."""

import logging


class GraphErrorFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if record.levelno >= logging.ERROR:
            record.msg = "Graph retrieval failed."
            record.args = ()
            record.exc_info = None
            record.exc_text = None
        return True


def configure_logging() -> None:
    logger = logging.getLogger("weave_brain.graph.queries")
    if not any(isinstance(item, GraphErrorFilter) for item in logger.filters):
        logger.addFilter(GraphErrorFilter())
