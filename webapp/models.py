from search import add_to_index, remove_from_index, make_query
from init_app import db, app
from sqlalchemy.sql import func

func.date()

db.Model.metadata.reflect(db.engine)


class SearchableMixin(object):
    @classmethod
    def get_monitoring_results(cls, query, page, per_page):
        if not query:
            filtered = cls.query.order_by(Bill.last_action_date.desc()).all()
            filtered = filtered[(page - 1)*per_page:(page - 1)*per_page+per_page]
            total = len(filtered)
        else:
            ids, total = make_query(cls.__tablename__, query, page, per_page)
            filtered = cls.query.filter(cls.id.in_(ids)).order_by(Bill.last_action_date.desc()).all()
            #filtered = cls.query.filter(cls.id.in_(ids)).all()
        return filtered, total
    
    @classmethod
    def before_commit(cls, session):
        session._changes = {
            'add': list(session.new),
            'update': list(session.dirty),
            'delete': list(session.deleted)
        }

    @classmethod
    def after_commit(cls, session):
        for obj in session._changes['add']:
            if isinstance(obj, SearchableMixin):
                add_to_index(obj.__tablename__, obj)
        for obj in session._changes['update']:
            if isinstance(obj, SearchableMixin):
                add_to_index(obj.__tablename__, obj)
        for obj in session._changes['delete']:
            if isinstance(obj, SearchableMixin):
                remove_from_index(obj.__tablename__, obj)
        session._changes = None

    @classmethod
    def reindex(cls):
        for obj in cls.query.all():
            add_to_index(cls.__tablename__, obj)
    

class Bill(SearchableMixin, db.Model):
    __searchable__ = ['title', 'subject', 'session', 'text', 'code', 
                      'authors', 'leginfo_id', 'last_action_date']
    __table__ = db.Model.metadata.tables['bills']
    
@classmethod
def reindex_by_leginfo_ids(cls, leginfo_ids):
    # sqlite doesn't allow very long queries
    # if we have a lot of ids in leginfo_ids and try to make query for all of
    # them at once, we'll get an error
    # so we query by parts
    
    # number of ids to query at once
    step = 20
    i = 0
    while i < len(leginfo_ids):
        ids_part = leginfo_ids[i:i+step]
        for obj in cls.query.filter(cls.leginfo_id.in_(ids_part)).all():
            add_to_index(cls.__tablename__, obj)
        i += step
        
Bill.reindex_by_leginfo_ids = reindex_by_leginfo_ids

def get_all_keywords():
    with open('keywords.txt', 'r') as f:
        return [kw.strip() for kw in f.read().splitlines() if kw.strip() != '']


if __name__ == "__main__":
    with app.app_context():
        per_page = 10
        page = 3
        offset = 10
        
        query = get_all_keywords()
            
        bills, total = Bill.get_monitoring_results(query, 
                                                   page=page, per_page=per_page)
