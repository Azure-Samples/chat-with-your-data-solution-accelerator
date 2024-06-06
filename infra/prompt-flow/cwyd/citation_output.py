from promptflow import tool


@tool
def my_python_tool(output) -> str:
    return output[1]
