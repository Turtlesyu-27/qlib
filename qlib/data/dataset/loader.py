# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import abc
import warnings
import pandas as pd

from typing import Tuple

from qlib.data import D


class DataLoader(abc.ABC):
    """
    DataLoader is designed for loading raw data from original data source.
    """
    @abc.abstractmethod
    def load(self, instruments, start_time=None, end_time=None) -> pd.DataFrame:
        """
        load the data as pd.DataFrame

        Parameters
        ----------
        self : [TODO:type]
            [TODO:description]
        instruments : [TODO:type]
            [TODO:description]
        start_time : [TODO:type]
            [TODO:description]
        end_time : [TODO:type]
            [TODO:description]

        Returns
        -------
        pd.DataFrame:
            data load from the under layer source

            Example of the data:
            (The multi-index of the columns is optional.)
                                    feature                                                             label
                                    $close     $volume     Ref($close, 1)  Mean($close, 3)  $high-$low  LABEL0
            datetime    instrument
            2010-01-04  SH600000    81.807068  17145150.0       83.737389        83.016739    2.741058  0.0032
                        SH600004    13.313329  11800983.0       13.313329        13.317701    0.183632  0.0042
                        SH600005    37.796539  12231662.0       38.258602        37.919757    0.970325  0.0289
        """
        pass


class DLWParser(DataLoader):
    """
    (D)ata(L)oader (W)ith (P)arser for features and names

    Extracting this class so that QlibDataLoader and other dataloaders(such as QdbDataLoader) can share the fields
    """
    def __init__(self, config: Tuple[list, tuple, dict]):
        """
        Parameters
        ----------
        config : Tuple[list, tuple, dict]
            Config will be used to describe the fields and column names

            <config> := {
                "group_name1": <fields_info1>
                "group_name2": <fields_info2>
            }
            or
            <config> := <fields_info>

            <fields_info> := ["expr", ...] | (["expr", ...], ["col_name", ...])
        """
        self.is_group = isinstance(config, dict)

        if self.is_group:
            self.fields = {grp: self._parse_fields_info(fields_info) for grp, fields_info in config.items()}
        else:
            self.fields = self._parse_fields_info(config)

    def _parse_fields_info(self, fields_info: Tuple[list, tuple]) -> Tuple[list, list]:
        if isinstance(fields_info, list):
            exprs = names = fields_info
        elif isinstance(fields_info, tuple):
            exprs, names = fields_info
        else:
            raise NotImplementedError(f"This type of input is not supported")
        return exprs, names

    @abc.abstractmethod
    def load_group_df(self, instruments, exprs: list, names: list, start_time=None, end_time=None) -> pd.DataFrame:
        """
        load the dataframe for specific group

        Parameters
        ----------
        instruments :
            the instruments
        exprs : list
            The expressions to describe the content of the data
        names : list
            The name of the data

        Returns
        -------
        pd.DataFrame:
            the queried dataframe
        """
        pass

    def load(self, instruments=None, start_time=None, end_time=None) -> pd.DataFrame:
        if self.is_group:
            df = pd.concat(
                {
                    grp: self.load_group_df(instruments, exprs, names, start_time, end_time)
                    for grp, (exprs, names) in self.fields.items()
                },
                axis=1)
        else:
            exprs, names = self.fields
            df = self.load_group_df(instruments, exprs, names, start_time, end_time)
        return df


class QlibDataLoader(DLWParser):
    """Same as QlibDataLoader. The fields can be define by config"""
    def __init__(self, config: Tuple[list, tuple, dict], filter_pipe=None):
        """
        Parameters
        ----------
        config : Tuple[list, tuple, dict]
            Please refer to the doc of DLWParser
        filter_pipe :
            Filter pipe for the instruments
        """
        self.filter_pipe = filter_pipe
        super().__init__(config)

    def load_group_df(self, instruments, exprs: list, names: list, start_time=None, end_time=None) -> pd.DataFrame:
        if isinstance(instruments, str):
            instruments = D.instruments(instruments, filter_pipe=self.filter_pipe)
        elif self.filter_pipe is not None:
            warnings.warn("`filter_pipe` is not None, but it will not be used with `instruments` as list")

        df = D.features(instruments, exprs, start_time, end_time)
        df.columns = names
        df = df.swaplevel().sort_index()  # NOTE: always return <datetime, instrument>
        return df