import datetime
import time
from dataclasses import dataclass
from typing import Optional, Dict, Annotated, Union, Literal, Iterable, List, Tuple
from uuid import UUID

from flask import Flask
from pydantic import BaseModel, Field
from requests import Session, Request

from notion_opds.ext import cache


class DatabaseProperty(BaseModel):
    id: str
    name: str
    type: Literal[
        'checkbox', 'created_by', 'created_time', 'date', 'email', 'files', 'formula', 'formula', 'last_edited_by',
        'last_edited_time', 'multi_select', 'number', 'people', 'phone_number', 'relation', 'rollup', 'rich_text',
        'title', 'url'
    ]


class SelectOption(BaseModel):
    id: str
    color: str
    name: str


class SelectPropertyType(DatabaseProperty):
    type: Literal['select', 'status']
    options: List[SelectOption]


class Database(BaseModel):
    id: UUID
    author_id: UUID
    created_at: datetime.datetime
    updated_at: datetime.datetime
    title: str
    description: Optional[str]
    properties: Dict[
        str,
        Annotated[
            Union[
                SelectPropertyType,
                DatabaseProperty
            ],
            Field(discriminator="type")
        ]
    ]


class Page(BaseModel):
    id: UUID
    author_id: UUID
    created_at: datetime.datetime
    updated_at: datetime.datetime

@dataclass
class NotionRateLimit:
    slots: int
    timestamp: datetime.datetime



class Notion:
    def __init__(self, app: Flask):
        self._session = Session()
        self._app = app
        self._session.headers.update({
            'Notion-Version': "2022-02-22",
            'Authorization': f"Bearer {self._app.config['NOTION_TOKEN']}"
        })
        self._base_url = 'https://api.notion.com'

    @staticmethod
    def _find_by_type(items: Iterable[Dict], query: str) -> Dict:
        return next(x for x in items if x["type"] == query)

    def _execute(self, request):
        # TODO: add to queue and wait
        r = self._session.send(request.prepare())
        r.raise_for_status()
        return r.json()

    @cache.cached(key_prefix='NotionDatabase')
    def get_database(self, database_id: str) -> Database:
        req = Request(
            'GET', f'{self._base_url}/v1/databases/{database_id}',
        )
        data = self._execute(req)

        properties = {}

        for item in data['properties'].values():
            match item['type']:
                case 'select' | 'status':
                    properties[item['name']] = SelectPropertyType(
                        id=item['id'],
                        name=item['name'],
                        type=item['type'],
                        options=[SelectOption.parse_obj(i) for i in item[item['type']]['options']]
                    )
                case _:
                    properties[item['name']] = DatabaseProperty(
                        id=item['id'],
                        name=item['name'],
                        type=item['type']
                    )

        return Database(
            id=data['id'],
            author_id=data['created_by']['id'],
            created_at=datetime.datetime.fromisoformat(data['created_time']),
            updated_at=datetime.datetime.fromisoformat(data['last_edited_time']),
            title=self._find_by_type(data['title'], 'text')['plain_text'],
            description=self._find_by_type(data['description'], 'text')['plain_text'],
            properties=properties
        )

    @cache.cached(key_prefix='NotionQuery')
    def query_database(
        self, database_id: str, conditions: dict, next_cursor: Optional[str]
    ) -> Tuple[Iterable[Page], Optional[str]]:
        payload = {
            'page_size': self._app.config['NOTION_PAGE_SIZE'],
            'filter': conditions
        }

        if next_cursor:
            payload['next_cursor'] = next_cursor

        req = Request(
            'POST', f"{self._base_url}/v1/databases/{database_id}/query",
            json=payload
        )
        data = self._execute(req)

        result = []

        for item in data.get('results'):
            result.append(Page(

            ))

        return result, data.get('next_cursor', None)

    @cache.cached(key_prefix='NotionPage')
    def get_page(self, page_id: str):
        ...
