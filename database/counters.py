from pymongo import ReturnDocument
from database.mongodb import db


def initialize_counter(counter_name, collection_name, id_field):
    """Initialize a counter without overwriting an existing counter."""

    highest_id = db[collection_name].find_one(
        sort=[(id_field, -1)],
        projection={id_field: 1}
    )

    starting_value = highest_id[id_field] if highest_id else 0

    db.counters.update_one(
        {"_id": counter_name},
        {"$max": {"sequence_value": starting_value}},
        upsert=True
    )


def get_next_sequence(counter_name):
    """Generate the next unique integer ID."""

    result = db.counters.find_one_and_update(
        {"_id": counter_name},
        {"$inc": {"sequence_value": 1}},
        upsert=True,
        return_document=ReturnDocument.AFTER
    )

    return result["sequence_value"]
