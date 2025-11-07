import logging
import sys
import colorama
import structlog


def custom_processor_merge_callsite(logger, method_name, event_dict: dict[str, str]):
    module = event_dict.get("module")
    filename = event_dict.get("filename")
    func_name = event_dict.get("func_name")
    lineno = event_dict.get("lineno")

    if module is None or filename is None or func_name is None or lineno is None:
        return event_dict

    event_dict["merged_callsite"] = "{0}/{1}:{2}:{3}".format(
        module, filename, func_name, lineno
    )
    event_dict.pop("module")
    event_dict.pop("filename")
    event_dict.pop("func_name")
    event_dict.pop("lineno")
    return event_dict


def logger_setup():
    logger_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.TimeStamper(fmt="iso", utc=False),
        structlog.processors.CallsiteParameterAdder(
            {
                structlog.processors.CallsiteParameter.MODULE,
                structlog.processors.CallsiteParameter.FILENAME,
                structlog.processors.CallsiteParameter.FUNC_NAME,
                structlog.processors.CallsiteParameter.LINENO,
            }
        ),
        custom_processor_merge_callsite,
        structlog.dev.set_exc_info,
    ]

    # Whether development environment
    if sys.stderr.isatty():
        logger_processors += [
            structlog.dev.ConsoleRenderer(
                columns=[
                    # Render the timestamp without the key name in yellow.
                    structlog.dev.Column(
                        "timestamp",
                        structlog.dev.KeyValueColumnFormatter(
                            key_style=None,
                            value_style=colorama.Fore.LIGHTBLACK_EX,
                            reset_style=colorama.Style.RESET_ALL,
                            value_repr=str,
                        ),
                    ),
                    # Log level
                    structlog.dev.Column(
                        "level",
                        structlog.dev.LogLevelColumnFormatter(
                            level_styles={
                                "debug": colorama.Fore.CYAN + colorama.Style.BRIGHT,
                                "info": colorama.Fore.GREEN + colorama.Style.BRIGHT,
                                "warning": colorama.Fore.YELLOW + colorama.Style.BRIGHT,
                                "error": colorama.Fore.RED + colorama.Style.BRIGHT,
                                "critical": colorama.Fore.MAGENTA
                                + colorama.Style.BRIGHT,
                            },
                            reset_style=colorama.Style.RESET_ALL,
                            width=8,
                        ),
                    ),
                    # Render the event without the key name in bright magenta.
                    structlog.dev.Column(
                        "event",
                        structlog.dev.KeyValueColumnFormatter(
                            key_style=None,
                            value_style=colorama.Fore.WHITE + colorama.Style.NORMAL,
                            reset_style=colorama.Style.RESET_ALL,
                            value_repr=str,
                        ),
                    ),
                    # Log location
                    structlog.dev.Column(
                        "merged_callsite",
                        structlog.dev.KeyValueColumnFormatter(
                            key_style=None,
                            value_style=colorama.Fore.BLUE + colorama.Style.NORMAL,
                            reset_style=colorama.Style.RESET_ALL,
                            value_repr=str,
                            prefix="->",
                            postfix="|",
                        ),
                    ),
                    # Default formatter for all keys not explicitly mentioned.
                    structlog.dev.Column(
                        "",
                        structlog.dev.KeyValueColumnFormatter(
                            key_style=colorama.Fore.CYAN + colorama.Style.BRIGHT,
                            value_style=colorama.Fore.MAGENTA + colorama.Style.BRIGHT,
                            reset_style=colorama.Style.RESET_ALL,
                            value_repr=str,
                        ),
                    ),
                ],
                exception_formatter=structlog.dev.RichTracebackFormatter(),
            ),
        ]
    else:
        logger_processors += [
            structlog.processors.JSONRenderer(),
        ]

    # StructLog config
    structlog.configure(
        processors=logger_processors,
        wrapper_class=structlog.make_filtering_bound_logger(logging.DEBUG),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
