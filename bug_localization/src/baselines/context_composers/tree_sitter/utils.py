from pathlib import Path

from tree_sitter import Language, Parser

BASE_DIR = Path(__file__).parent.resolve()

# Build the Java language library
Language.build_library(
    BASE_DIR / "tree-sitter-java.so",  # Output file
    [BASE_DIR / "tree-sitter-java"]  # Source folder
)

JAVA_LANGUAGE = Language(BASE_DIR / "tree-sitter-java.so", "java")

# Build the Kotlin language library
Language.build_library(
    BASE_DIR / "tree-sitter-kotlin.so",  # Output file
    [BASE_DIR / "tree-sitter-kotlin"]  # Source folder
)
KOTLIN_LANGUAGE = Language(BASE_DIR / "tree-sitter-kotlin.so", "kotlin")

# Build the Python language library
Language.build_library(
    BASE_DIR / "tree-sitter-python.so",  # Output file
    [BASE_DIR / "tree-sitter-python"]  # Source folder
)
PYTHON_LANGUAGE = Language(BASE_DIR / "tree-sitter-python.so", "python")


def get_parser(language):
    parser = Parser()
    parser.set_language(language)
    return parser


# Extraction logic for Python
def extract_python_imports(source_code):
    parser = get_parser(PYTHON_LANGUAGE)
    tree = parser.parse(source_code.encode())
    root_node = tree.root_node

    imports = []
    for import_statement in root_node.children:
        if import_statement.type == 'import_statement':  # Example: `import math`
            imports.append(import_statement.text.decode('utf-8'))
        elif import_statement.type == 'import_from_statement':  # Example: `from os import path`
            imports.append(import_statement.text.decode('utf-8'))
    return imports


# Extraction logic for Java
def extract_java_imports(source_code):
    parser = get_parser(JAVA_LANGUAGE)
    tree = parser.parse(source_code.encode())
    root_node = tree.root_node

    imports = []
    for node in root_node.children:
        if node.type == 'import_declaration':  # Example: `import java.util.List`
            imports.append(source_code[node.start_byte:node.end_byte - 1])
    return imports


# Extraction logic for Kotlin
def extract_kotlin_imports(source_code):
    parser = get_parser(KOTLIN_LANGUAGE)
    tree = parser.parse(source_code.encode())
    root_node = tree.root_node

    imports = []
    for node in root_node.children:
        if node.type == 'import_list':  # Example: `import kotlin.collections.List`
            for import_declaration in node.children:
                imports.append(source_code[import_declaration.start_byte:import_declaration.end_byte])
    return imports


# Universal extraction based on file type
def extract_imports(source_code: str, file_extension: str):
    if file_extension == 'py':
        return extract_python_imports(source_code)
    elif file_extension == 'java':
        return extract_java_imports(source_code)
    elif file_extension == 'kt':
        return extract_kotlin_imports(source_code)
    else:
        # TODO: raise exception?
        return []



def _node_text(node) -> str:
    return node.text.decode("utf-8")


def _python_signature(node) -> str:
    parts: list[str] = []

    # Collect decorators that appear the node in the parent's children
    if node.parent is not None:
        for sibling in node.parent.children:
            if sibling.type == "decorator" and sibling.end_point[0] < node.start_point[0]:
                # Only keep decorators immediately preceding this node
                if sibling.end_point[0] >= node.start_point[0] - 2:
                    parts.append(_node_text(sibling))

    if node.type == "class_definition":
        # class ClassName(bases):
        name = node.child_by_field_name("name")
        superclasses = node.child_by_field_name("superclasses")
        sig = f"class {_node_text(name)}" if name else "class ?"
        if superclasses:
            sig += _node_text(superclasses)
        parts.append(sig)
    elif node.type == "function_definition":
        # def func_name(params) -> return_type:
        name = node.child_by_field_name("name")
        params = node.child_by_field_name("parameters")
        ret = node.child_by_field_name("return_type")
        sig = f"def {_node_text(name)}" if name else "def ?"
        sig += _node_text(params) if params else "()"
        if ret:
            sig += f" -> {_node_text(ret)}"
        parts.append(sig)

    return "\n".join(parts)


def extract_python_signatures(source_code: str) -> list[str]:
    parser = get_parser(PYTHON_LANGUAGE)
    tree = parser.parse(source_code.encode())
    sigs: list[str] = []

    def _walk(node, depth=0):
        if node.type in ("function_definition", "class_definition"):
            indent = "    " * depth
            sig = _python_signature(node)
            for line in sig.split("\n"):
                sigs.append(f"{indent}{line}")
            # Recurse into class bodies to get methods
            if node.type == "class_definition":
                body = node.child_by_field_name("body")
                if body:
                    for child in body.children:
                        _walk(child, depth + 1)
        else:
            for child in node.children:
                _walk(child, depth)

    _walk(tree.root_node)
    return sigs


def _java_signature(node, source_code: str) -> str:
    if node.type == "class_declaration":
        for child in node.children:
            if child.type == "class_body":
                return source_code[node.start_byte:child.start_byte].strip()
        return source_code[node.start_byte:node.end_byte].split("{")[0].strip()

    if node.type == "interface_declaration":
        for child in node.children:
            if child.type == "interface_body":
                return source_code[node.start_byte:child.start_byte].strip()
        return source_code[node.start_byte:node.end_byte].split("{")[0].strip()

    if node.type in ("method_declaration", "constructor_declaration"):
        for child in node.children:
            if child.type == "block":
                return source_code[node.start_byte:child.start_byte].strip()
        return source_code[node.start_byte:node.end_byte].split("{")[0].strip()

    return ""


def extract_java_signatures(source_code: str) -> list[str]:
    parser = get_parser(JAVA_LANGUAGE)
    tree = parser.parse(source_code.encode())
    sigs: list[str] = []
    target_types = {
        "class_declaration", "interface_declaration",
        "method_declaration", "constructor_declaration",
    }

    def _walk(node, depth=0):
        if node.type in target_types:
            indent = "    " * depth
            sig = _java_signature(node, source_code)
            if sig:
                sigs.append(f"{indent}{sig}")
            # Recurse into class/interface bodies
            if node.type in ("class_declaration", "interface_declaration"):
                for child in node.children:
                    if child.type in ("class_body", "interface_body"):
                        for member in child.children:
                            _walk(member, depth + 1)
        else:
            for child in node.children:
                _walk(child, depth)

    _walk(tree.root_node)
    return sigs


def _kotlin_signature(node, source_code: str) -> str:
    if node.type == "class_declaration":
        for child in node.children:
            if child.type == "class_body":
                return source_code[node.start_byte:child.start_byte].strip()
        return source_code[node.start_byte:node.end_byte].split("{")[0].strip()

    if node.type == "function_declaration":
        for child in node.children:
            if child.type == "function_body":
                return source_code[node.start_byte:child.start_byte].strip()
        return source_code[node.start_byte:node.end_byte].split("{")[0].strip()

    return ""


def extract_kotlin_signatures(source_code: str) -> list[str]:
    parser = get_parser(KOTLIN_LANGUAGE)
    tree = parser.parse(source_code.encode())
    sigs: list[str] = []
    target_types = {"class_declaration", "function_declaration"}

    def _walk(node, depth=0):
        if node.type in target_types:
            indent = "    " * depth
            sig = _kotlin_signature(node, source_code)
            if sig:
                sigs.append(f"{indent}{sig}")
            if node.type == "class_declaration":
                for child in node.children:
                    if child.type == "class_body":
                        for member in child.children:
                            _walk(member, depth + 1)
        else:
            for child in node.children:
                _walk(child, depth)

    _walk(tree.root_node)
    return sigs


def extract_signatures(source_code: str, file_extension: str) -> list[str]:
    if file_extension == "py":
        return extract_python_signatures(source_code)
    elif file_extension == "java":
        return extract_java_signatures(source_code)
    elif file_extension == "kt":
        return extract_kotlin_signatures(source_code)
    else:
        return []
