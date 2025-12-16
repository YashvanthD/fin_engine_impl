class FishMappingRepository:
    def __init__(self, collection):
        self.collection = collection

    def update_one(self, *args, **kwargs):
        return self.collection.update_one(*args, **kwargs)

    def find_one(self, *args, **kwargs):
        return self.collection.find_one(*args, **kwargs)
    # Add more methods as needed
