import datetime
import hashlib
import os
import traceback

from .DisassemblyStatistics import DisassemblyStatistics
from .intel.IntelDisassembler import IntelDisassembler
from .ida.IdaExporter import IdaExporter
from smda.utility.FileLoader import FileLoader

class Disassembler(object):

    def __init__(self, config, backend="intel"):
        self.config = config
        self.disassembler = None
        if backend == "intel":
            self.disassembler = IntelDisassembler(config)
        elif backend == "IDA":
            self.disassembler = IdaExporter(config)
        self.disassembly = None
        self._start_time = None
        self._timeout = 0

    def _getDurationInSeconds(self, start_ts, end_ts):
        return (self.analysis_end_ts - self.analysis_start_ts).seconds + ((self.analysis_end_ts - self.analysis_start_ts).microseconds / 1000000.0)

    def _callbackAnalysisTimeout(self):
        if not self._timeout:
            return False
        time_diff = datetime.datetime.utcnow() - self._start_time
        return time_diff.seconds >= self._timeout

    def disassembleFile(self, file_path, pdb_path=""):
        loader = FileLoader(file_path, map_file=True)
        base_addr = loader.getBaseAddress()
        bitness = loader.getBitness()
        file_content = loader.getData()
        start = datetime.datetime.utcnow()
        try:
            self.disassembler.setFilePath(file_path)
            self.disassembler.addPdbFile(pdb_path, base_addr)
            print("Disassembler uses base address: 0x%x and bitness: %dbit" % (base_addr, bitness))
            disassembly = self.disassemble(file_content, base_addr, bitness=bitness, timeout=self.config.TIMEOUT)
            report = self.getDisassemblyReport(disassembly)
            report["filename"] = os.path.basename(file_path)
            print(disassembly)
        except Exception as exc:
            print("-> an error occured (", str(exc), ").")
            report = {"status":"error", "meta": {"traceback": traceback.format_exc(exc)}, "execution_time": self._getDurationInSeconds(start, datetime.datetime.utcnow())}
        return report

    def disassembleBuffer(self, file_content, base_addr, bitness=None):
        start = datetime.datetime.utcnow()
        try:
            self.disassembler.setFilePath("")
            disassembly = self.disassemble(file_content, base_addr, bitness, timeout=self.config.TIMEOUT)
            report = self.getDisassemblyReport(disassembly)
            report["filename"] = ""
            print(disassembly)
        except Exception as exc:
            print("-> an error occured (", str(exc), ").")
            report = {"status":"error", "meta": {"traceback": traceback.format_exc(exc)}, "execution_time": self._getDurationInSeconds(start, datetime.datetime.utcnow())}
        return report

    def disassemble(self, binary, base_addr, bitness=None, timeout=0):
        self._start_time = datetime.datetime.utcnow()
        self._timeout = timeout
        self.disassembly = self.disassembler.analyzeBuffer(binary, base_addr, bitness, self._callbackAnalysisTimeout)
        return self.disassembly

    def getDisassemblyReport(self, disassembly=None):
        report = {}
        if disassembly is None:
            if self.disassembly is not None:
                disassembly = self.disassembly
            else:
                return {}
        stats = DisassemblyStatistics(disassembly)
        report = {
            "architecture": disassembly.architecture,
            "base_addr": disassembly.base_addr,
            "bitness": disassembly.bitness,
            "buffer_size": len(disassembly.binary),
            "disassembly_errors": disassembly.errors,
            "execution_time": disassembly.getAnalysisDuration(),
            "metadata" : {
                "message": "Analysis finished regularly."
            },
            "sha256": hashlib.sha256(disassembly.binary).hexdigest(),
            "smda_version": self.config.VERSION,
            "status": disassembly.getAnalysisOutcome(),
            "summary": stats.calculate(),
            "timestamp": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H-%M-%S"),
            "xcfg": disassembly.collectCfg(),
        }
        return report
