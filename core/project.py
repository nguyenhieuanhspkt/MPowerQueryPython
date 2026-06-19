import json
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional, Any, Union


# ---------------------------------------------------------------------------
# Source types
# ---------------------------------------------------------------------------

@dataclass
class FileSource:
    path: str
    sheet_name: Optional[str] = None
    decimal: str = ','
    csv_sep: str = 'auto'

    def to_dict(self) -> dict:
        return {'type': 'file', 'path': self.path,
                'sheet_name': self.sheet_name,
                'decimal': self.decimal, 'csv_sep': self.csv_sep}

    @staticmethod
    def from_dict(d: dict) -> 'FileSource':
        return FileSource(path=d['path'], sheet_name=d.get('sheet_name'),
                          decimal=d.get('decimal', ','),
                          csv_sep=d.get('csv_sep', 'auto'))


@dataclass
class QuerySource:
    """Passthrough — takes output of another query as input."""
    query_name: str

    def to_dict(self) -> dict:
        return {'type': 'query', 'query': self.query_name}

    @staticmethod
    def from_dict(d: dict) -> 'QuerySource':
        return QuerySource(query_name=d['query'])


@dataclass
class MergeSource:
    """pd.merge of two query outputs."""
    left: str
    right: str
    on: str
    how: str = 'left'

    def to_dict(self) -> dict:
        return {'type': 'merge', 'left': self.left, 'right': self.right,
                'on': self.on, 'how': self.how}

    @staticmethod
    def from_dict(d: dict) -> 'MergeSource':
        return MergeSource(left=d['left'], right=d['right'],
                           on=d['on'], how=d.get('how', 'left'))


@dataclass
class AppendSource:
    """pd.concat (row-wise) of N query outputs."""
    queries: List[str]

    def to_dict(self) -> dict:
        return {'type': 'append', 'queries': list(self.queries)}

    @staticmethod
    def from_dict(d: dict) -> 'AppendSource':
        return AppendSource(queries=list(d['queries']))


AnySource = Union[FileSource, QuerySource, MergeSource, AppendSource]


def _source_from_dict(d: dict) -> AnySource:
    t = d.get('type', 'file')
    if t == 'file':
        return FileSource.from_dict(d)
    if t == 'query':
        return QuerySource.from_dict(d)
    if t == 'merge':
        return MergeSource.from_dict(d)
    if t == 'append':
        return AppendSource.from_dict(d)
    raise ValueError(f'Unknown source type: {t!r}')


# ---------------------------------------------------------------------------
# QueryDef — one query in the project
# ---------------------------------------------------------------------------

class QueryDef:
    def __init__(self, name: str, source: AnySource,
                 recipe_steps: Optional[List[Dict[str, Any]]] = None):
        self.name = name
        self.source = source
        self.recipe_steps: List[Dict[str, Any]] = recipe_steps or []

    def dependencies(self) -> List[str]:
        """Return names of queries this query directly depends on."""
        s = self.source
        if isinstance(s, FileSource):
            return []
        if isinstance(s, QuerySource):
            return [s.query_name]
        if isinstance(s, MergeSource):
            return [s.left, s.right]
        if isinstance(s, AppendSource):
            return list(s.queries)
        return []

    def to_dict(self) -> dict:
        return {
            'name': self.name,
            'source': self.source.to_dict(),
            'recipe_steps': self.recipe_steps,
        }

    @staticmethod
    def from_dict(d: dict) -> 'QueryDef':
        return QueryDef(
            name=d['name'],
            source=_source_from_dict(d['source']),
            recipe_steps=d.get('recipe_steps', []),
        )


# ---------------------------------------------------------------------------
# Project — container for all queries
# ---------------------------------------------------------------------------

class Project:
    VERSION = 1

    def __init__(self, name: str = 'Untitled'):
        self.name = name
        self.path: Optional[str] = None          # .mpq file path if saved
        self._queries: List[QueryDef] = []       # ordered list
        self.active_query: Optional[str] = None  # name of active query

    # ---------------------------------------------------------------- queries

    def query_names(self) -> List[str]:
        return [q.name for q in self._queries]

    def get_query(self, name: str) -> QueryDef:
        for q in self._queries:
            if q.name == name:
                return q
        raise KeyError(f'Query not found: {name!r}')

    def add_query(self, query: QueryDef):
        if query.name in self.query_names():
            raise ValueError(f'Query name already exists: {query.name!r}')
        if self._would_create_cycle_if_added(query):
            raise ValueError(f'Adding query {query.name!r} would create a cycle.')
        self._queries.append(query)
        if self.active_query is None:
            self.active_query = query.name

    def remove_query(self, name: str):
        dependents = self.downstream(name)
        if dependents:
            raise ValueError(
                f'Cannot remove "{name}" — the following queries depend on it: '
                + ', '.join(f'"{d}"' for d in dependents))
        self._queries = [q for q in self._queries if q.name != name]
        if self.active_query == name:
            self.active_query = self._queries[0].name if self._queries else None

    def rename_query(self, old_name: str, new_name: str):
        if new_name in self.query_names():
            raise ValueError(f'Name already taken: {new_name!r}')
        for q in self._queries:
            if q.name == old_name:
                q.name = new_name
            # patch references in other queries' sources
            s = q.source
            if isinstance(s, QuerySource) and s.query_name == old_name:
                s.query_name = new_name
            elif isinstance(s, MergeSource):
                if s.left == old_name:
                    s.left = new_name
                if s.right == old_name:
                    s.right = new_name
            elif isinstance(s, AppendSource):
                s.queries = [new_name if n == old_name else n for n in s.queries]
        if self.active_query == old_name:
            self.active_query = new_name

    # ---------------------------------------------------------------- DAG

    def dependencies(self, name: str) -> List[str]:
        """Direct dependencies of a query."""
        return self.get_query(name).dependencies()

    def downstream(self, name: str) -> List[str]:
        """All queries that (directly or transitively) depend on `name`."""
        result = []
        for q in self._queries:
            if name in q.dependencies():
                result.append(q.name)
                result.extend(self.downstream(q.name))
        return list(dict.fromkeys(result))  # deduplicate preserving order

    def topo_order(self) -> List[str]:
        """Topological sort — upstream first, downstream last."""
        visited: set = set()
        order: List[str] = []

        def _visit(name: str):
            if name in visited:
                return
            visited.add(name)
            for dep in self.dependencies(name):
                _visit(dep)
            order.append(name)

        for q in self._queries:
            _visit(q.name)
        return order

    def has_cycle(self) -> bool:
        visiting: set = set()
        visited: set = set()

        def _dfs(name: str) -> bool:
            if name in visiting:
                return True  # back-edge → cycle
            if name in visited:
                return False
            visiting.add(name)
            for dep in self.dependencies(name):
                if dep in self.query_names() and _dfs(dep):
                    return True
            visiting.discard(name)
            visited.add(name)
            return False

        return any(_dfs(q.name) for q in self._queries)

    def _would_create_cycle_if_added(self, new_query: QueryDef) -> bool:
        # Temporarily add and check
        self._queries.append(new_query)
        result = self.has_cycle()
        self._queries.pop()
        return result

    # ---------------------------------------------------------------- serialize

    def to_dict(self) -> dict:
        return {
            'version': self.VERSION,
            'name': self.name,
            'active_query': self.active_query,
            'queries': [q.to_dict() for q in self._queries],
        }

    def save(self, path: str):
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)
        self.path = path

    @classmethod
    def load(cls, path: str) -> 'Project':
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        proj = cls(name=data.get('name', 'Untitled'))
        proj.path = path
        proj._queries = [QueryDef.from_dict(qd) for qd in data.get('queries', [])]
        proj.active_query = data.get('active_query')
        if proj.active_query not in proj.query_names() and proj._queries:
            proj.active_query = proj._queries[0].name
        return proj

    # ---------------------------------------------------------------- unique name helper

    def unique_query_name(self, base: str) -> str:
        names = set(self.query_names())
        if base not in names:
            return base
        i = 1
        while f'{base}_{i}' in names:
            i += 1
        return f'{base}_{i}'


# ---------------------------------------------------------------------------
# Recent projects registry  (config/recent.json)
# ---------------------------------------------------------------------------

import os

_RECENT_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), 'config', 'recent.json')
_MAX_RECENT = 10


def recent_projects() -> List[str]:
    try:
        with open(_RECENT_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def push_recent(path: str):
    paths = [p for p in recent_projects() if p != path]
    paths.insert(0, path)
    os.makedirs(os.path.dirname(_RECENT_PATH), exist_ok=True)
    with open(_RECENT_PATH, 'w', encoding='utf-8') as f:
        json.dump(paths[:_MAX_RECENT], f, indent=2, ensure_ascii=False)
