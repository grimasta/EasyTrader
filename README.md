# $$ EASY TRADER $$

Author: grimasta

#### EasyTrader 0.01: 2026-09-02


## Purpose

### What EasyTrader is NOT
- - -
This tool is **NOT** supposed to make you money.

The strategies available here will not be profitable.

The purpose of this tool is to help you learn 
how trading works and why it is not a _get-rich-quick-thing_.

## What is EasyTrader
- - - 
1) An automated trading tool.
2) A trading strategy tester
3) A tool to learn how to trade using an algorithm (automated strategy).
4) A tool to evaluate strategies using backtesting and paper-trading.
5) A tool to lose money if you don't know how to trade
6) A tool to be hacked if you don't understand how API keys work, and you write them down, post then online, or 
otherwise mess up custody of your API keys.

 - - - 

### This tool comes with no warranty and no guarantees of any kind.

The source will be available on GitHub by grimasta. 100% free.
https://github.com/grimasta/EasyTrader

## Features

EasyTrader is a python tool. It is structured as a standalone installable app with a GUI and CLI. 
This is version 0.01; essentially nothing is currently implemented that would make this a product quality code.
Current features include:
Bitget API support for live/paper trading, and backtesting using inefficient pickle-based persistence.
Manual Strategy extension via writing code.
Manual Indicator extension via writing code.

## Architecture

The system will have a decoupled architecture.
The core will be a robust Data Model. The Data Model will be designed so that it will be able to consume and represent 
perpetual futures instruments from different exchanges.

The API clients will be designed to adhere to one uniform interface towards the Data Model.

The Trading Engine will consume the data model, request data, and execute orders.
The Trading Engine will use a separate persistence layer to persist its operation and will emit monitoring information 
for ongoing trades, running PnLs and other metrics yet to be defined.

The CLI and GUI will allow users to set up their instance of the tool.
Both the CLI and GUI will be used to populate a configuration file which will include your API keys (secrets). Those 
will be stored in an .env file that will be instantiated before running the tool. All keys will be deleted after 
intentional or accidental termination unless explicitly requested otherwise. 

## Road Map
1) Implement a Data Model that can consume and represent perpetual futures crypto-instruments from different exchanges.
2) Clean up the venues/bitget code and completely decouple from data and trading engine.
3) Implement a Parquet persistence layer for fetched data.
4) Extract API interface
5) Clean up and refactor the trading engine to decouple from venue/bitget, and force it to work only with the 
Data Model.

