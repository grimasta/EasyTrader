from core.data_model.instruments.abstract_instrument import Instrument
import pickle


class ConcreteInstrument(Instrument):

    def __init__(self, name):
        self.name = name
        self.restore_obj()
        self._5m = None
        self._15m = None
        self._30m = None
        self._1h = None
        self._2h = None
        self._4h = None
        self._8h = None
        self._1D = None
        self._2D = None
        self._1W = None
        self._2W = None
        self._1M = None
        self.BBs = None
        self.MAs = None

    def calculate_bb(self, bb_visitor):
        # super().calculate_bb()
        bb_visitor(self._5m, 14, 2)

    def set_5m(self, tf5m):
        self._5m = tf5m

    def calculate_tfs_from_5m(self):
        super().calculate_tfs_from_5m()

    def calculate_mas(self, MA_visitor):
        MA_visitor()
        # super().calculate_mas()

    def store_obj(self):
        import os
        target_dir = "../saved_instruments/"
        if not os.path.isdir(target_dir):\
            os.makedirs(target_dir)

        with open(target_dir + self.name + ".pkl", 'wb') as object_writer:
            pickle.dump(self, object_writer, pickle.HIGHEST_PROTOCOL)

    def restore_obj(self):
        import os
        source_dir = "../saved_instruments/"
        if os.path.exists(source_dir + self.name + ".pkl"):
            with open(source_dir + self.name + ".pkl", 'rb') as object_reader:
                loaded = pickle.load(object_reader)
            # self.name = loaded.name
            self._5m = loaded._5m
            self._15m = loaded._15m
            self._30m = loaded._30m
            self._1h = loaded._1h
            self._2h = loaded._2h
            self._4h = loaded._4h
            self._8h = loaded._8h
            self._1D = loaded._1D
            self._2D = loaded._2D
            self._1W = loaded._1W
            self._2W = loaded._2W
            self._1M = loaded._1M
            self.BBs = loaded.BBs
            self.MAs = loaded.MAs

