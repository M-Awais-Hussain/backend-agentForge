import lizard
from typing import Dict, Any

def analyze_complexity(code: str, language: str) -> Dict[str, Any]:
    ext_map = {
        "python": "py",
        "javascript": "js",
        "java": "java",
        "cpp": "cpp",
        "c": "c",
        "typescript": "ts"
    }
    ext = ext_map.get(language.lower(), "txt")
    filename = f"temp.{ext}"
    
    try:
        i = lizard.analyze_file.analyze_source_code(filename, code)
        metrics = {
            "nloc": i.nloc,
            "token_count": i.token_count,
            "average_cyclomatic_complexity": i.average_cyclomatic_complexity,
            "functions": []
        }
        for func in i.function_list:
            metrics["functions"].append({
                "name": func.name,
                "cyclomatic_complexity": func.cyclomatic_complexity,
                "nloc": func.nloc,
                "parameters": len(func.parameters)
            })
        return metrics
    except Exception as e:
        return {"error": str(e), "nloc": 0, "token_count": 0, "average_cyclomatic_complexity": 0, "functions": []}
