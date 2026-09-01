from abc import ABC


class Instrument(ABC):

    def calculate_bb(self, BB_Visitor):
        pass

    def calculate_tfs_from_5m(self):
        pass

    def calculate_mas(self, MA_visitor):
        pass

    def store_obj(self):
        pass

    def restore_obj(self, path):
        pass

