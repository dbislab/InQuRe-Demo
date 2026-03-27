# Intent Based Query Rewriting in Action

This repository contains the UI implementation for the Paper "Intent Based Query Rewriting in Action" by G. Nicolai, P. Hansert and S. Michel.

## Paper Abstract

We demonstrate a first solution to the task of intent-based query rewriting, where the aim is to allow rewrites to produce results different from the original query while keeping the obtainable insights intact. This differs drastically from traditional query rewriting, which typically aims to decrease query evaluation time by applying strict equivalence rules and optimization heuristics on the query plan. Intent-based query rewriting offers the ultimate promise of enabling access to otherwise inaccessible information by rephrasing queries over tables the user does not have access to, resorting to results from accessible tables. With this demonstration, we enable users to experience the concept of intent-based rewriting and explore the meaning and impact of the internal mechanisms of our approach called INQURE. Users may delete tables from a predefined set and issue arbitrary SQL queries referencing those tables. They can then inspect the results of the rewrites and compare them to the output of the original query to see if the intent was kept. Internally, the system can be configured to use alternate implementations of the individual processing steps, allowing users to understand how different algorithms affect the rewrite accuracy vs the monetary cost (of using an LLM) and runtime.


# Installation

Python version: 3.12<br>
Most Requirements can be found in requirements.txt

In addition, you need a working checkout of the INQURE repository found at [https://github.com/dbislab/InQuRe](https://github.com/dbislab/InQuRe).
Follow the instructions there to install it and then set the path in `config.json`.
Be sure to run the demonstrator from the same virtual environment

To avoid dependencies on external infratructure, our demonstrator locally embeds fonts and javascript libraries instead of relying on a CDN.
To run it successfully, download the following files and place them in the `static` diectory
* socket.io.js (see [Socket.IO Configuration](https://socket.io/docs/v4/tutorial/step-3))
* RedHatMono-Regular.ttf (optional, e.g. [Google Fonts](https://fonts.google.com/specimen/Red+Hat+Text?preview.script=Latn))
* RedHatText-Regular.ttf (optional, e.g. [Google Fonts](https://fonts.google.com/specimen/Red+Hat+Text?preview.script=Latn))

We assume the demonstrator is run on a modern filesystem which supports reflinks.
If your filesystem does not support reflink, you can remove it from the requirements file and change __enter__ in db_utils.py to use the os link instead of the reflink (commented out in the code).
Do so at your own risk.

## Database

A working DuckDB database is needed for the execution (has to be given with its path in the config).
It is possible to use any wanted schema in the database for this. 
The databases from the Paper can be found via their respective links in the Paper.
The file has to end in '.db'.
If there are no tables in the database, an error will be thrown, as no executable queries can be produced then.

## Config File

- Edit the database path to lead to the .db file of the database.
- The rewriter path must be set to the folder of InQuRe which can be downloaded here: https://github.com/dbislab/InQuRe (make sure to use the demo branch)
- temp_dir must be set to a folder that exists in your file system. It must be part of the same filesystem your database files reside on, setting it to tmpfs will not suffice.
- Other things like default queries etc. can also be added/changed in the config file


## Running the program

To run the UI run `flash run` from withn your python virtualenv



