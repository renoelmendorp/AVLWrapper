"""AVLWrapper exceptions"""


class AvlError(Exception):
    """Base class for all AVLWrapper errors"""


class InputError(AvlError, ValueError):
    """Invalid input

    :param lines_in: either a message, or the offending input lines
    """

    def __init__(self, lines_in):
        if isinstance(lines_in, str):
            msg = lines_in
        else:
            full_str = "\n".join(str(line) for line in lines_in)
            msg = f"Invalid input:\n{full_str}"
        super().__init__(msg)


class AvlExecutionError(AvlError):
    """AVL did not run successfully

    :param str message: what went wrong
    :param str output: output of AVL (stdout and stderr)
    """

    TAIL_LINES = 30

    def __init__(self, message, output=""):
        self.output = output
        tail = "\n".join(output.splitlines()[-self.TAIL_LINES :])
        if tail:
            message = f"{message}\nLast output of AVL:\n{tail}"
        super().__init__(message)


class OutputError(AvlError):
    """AVL output file could not be parsed"""


class AvlVersionError(AvlExecutionError):
    """The AVL version is not supported, or could not be determined"""
