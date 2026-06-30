"""Skill canonicalization: map aliases/variants to a canonical name."""
from typing import Optional

# canonical_name -> [aliases, ...]
_SKILL_MAP: dict[str, list[str]] = {
    "Python": ["python", "python3", "py", "python 3"],
    "JavaScript": ["javascript", "js", "javascript (es6)", "ecmascript", "es6", "es2015"],
    "TypeScript": ["typescript", "ts"],
    "Java": ["java", "java8", "java 8", "java 11"],
    "Go": ["go", "golang"],
    "Rust": ["rust", "rust-lang"],
    "C++": ["c++", "cpp", "c/c++"],
    "C#": ["c#", "csharp", "c sharp"],
    "Ruby": ["ruby", "ruby on rails"],
    "PHP": ["php"],
    "Swift": ["swift"],
    "Kotlin": ["kotlin"],
    "Scala": ["scala"],
    "R": ["r", "r language"],
    "SQL": ["sql", "mysql", "postgresql", "postgres", "sqlite", "t-sql", "pl/sql"],
    "NoSQL": ["nosql", "mongodb", "cassandra", "dynamodb", "couchdb"],
    "React": ["react", "reactjs", "react.js"],
    "Vue.js": ["vue", "vuejs", "vue.js"],
    "Angular": ["angular", "angularjs", "angular.js"],
    "Node.js": ["node", "nodejs", "node.js"],
    "Django": ["django"],
    "Flask": ["flask"],
    "FastAPI": ["fastapi"],
    "Spring": ["spring", "spring boot", "springboot"],
    "Docker": ["docker"],
    "Kubernetes": ["kubernetes", "k8s"],
    "AWS": ["aws", "amazon web services", "amazon aws"],
    "GCP": ["gcp", "google cloud", "google cloud platform"],
    "Azure": ["azure", "microsoft azure"],
    "Terraform": ["terraform"],
    "Git": ["git", "github", "gitlab", "version control"],
    "Linux": ["linux", "unix"],
    "Machine Learning": ["machine learning", "ml", "deep learning", "dl"],
    "TensorFlow": ["tensorflow", "tf"],
    "PyTorch": ["pytorch", "torch"],
    "Pandas": ["pandas"],
    "NumPy": ["numpy"],
    "REST API": ["rest", "rest api", "restful", "restful api"],
    "GraphQL": ["graphql"],
    "Redis": ["redis"],
    "Kafka": ["kafka", "apache kafka"],
    "Elasticsearch": ["elasticsearch", "elastic search", "elastic"],
    "CI/CD": ["ci/cd", "ci cd", "continuous integration", "continuous deployment", "jenkins", "github actions"],
    "Agile": ["agile", "scrum", "kanban"],
}

# Build reverse lookup: alias -> canonical
_ALIAS_TO_CANONICAL: dict[str, str] = {}
for _canonical, _aliases in _SKILL_MAP.items():
    _ALIAS_TO_CANONICAL[_canonical.lower()] = _canonical
    for _alias in _aliases:
        _ALIAS_TO_CANONICAL[_alias.lower()] = _canonical


def canonicalize_skill(raw: str) -> Optional[str]:
    if not raw or not raw.strip():
        return None
    return _ALIAS_TO_CANONICAL.get(raw.strip().lower(), raw.strip().title())


def canonicalize_skills(raws: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for r in raws:
        c = canonicalize_skill(r)
        if c and c not in seen:
            seen.add(c)
            result.append(c)
    return result
