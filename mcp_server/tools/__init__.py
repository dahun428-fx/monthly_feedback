import pkgutil
import importlib

TOOLS = {}
DESCRIPTIONS = []

# 현재 패키지(mcp_server.tools) 내의 모든 모듈 탐색
package = __name__

for loader, module_name, is_pkg in pkgutil.iter_modules(__path__):
    if module_name == "__init__":
        continue

    module = importlib.import_module(f"{package}.{module_name}")

    # run 함수가 있으면 툴로 등록
    if hasattr(module, "run"):
        TOOLS[module_name] = module.run

    # DESCRIPTION이 있으면 설명서에 추가
    if hasattr(module, "DESCRIPTION"):
        DESCRIPTIONS.append(module.DESCRIPTION)

DESCRIPTIONS = "\n".join(DESCRIPTIONS)

__all__ = ["TOOLS", "DESCRIPTIONS"]
