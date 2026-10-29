# Copyright (c) 2026 Manuel Hilgert
# See the file LICENSE.txt for your full rights.
"""Stage an import and aggregate observations into existing archive records."""

import collections
import json
import math
import sqlite3
import tempfile

import weeimport.weeimport
import weeutil.weeutil
import weewx.accum
import weewx.schemas.wview_extended


SPECIAL_FIELDS = ('dateTime', 'usUnits', 'interval')
WIND_FIELDS = ('windDir', 'windGust', 'windGustDir')


def _quote(name):
    return '`%s`' % name.replace('`', '``')


def _display(value):
    return 'NULL' if value is None else str(value)


def _encode(record):
    # A corrupt old value can still be shown and replaced by a valid import.
    return json.dumps(record, default=str)


class ArchiveAggregation:
    """Keep import-sized state on disk and validate every result before writing.

    Args:
        source (weeimport.weeimport.Source): Initialized import source with its field map.
        directory (str): Private temporary directory used only for this import.
    """

    def __init__(self, source, directory):
        self.source = source
        self.fields = [field for field in source.map if field not in SPECIAL_FIELDS]
        self.counts = collections.Counter()
        self.first_target = None
        self.last_target = None
        options = source.aggregation_options
        self.alignment = options.get('alignment', 'interval')
        if self.alignment not in ('interval', 'nearest', 'previous', 'next'):
            raise weeimport.weeimport.WeeImportOptionError('Unknown UpdateAggregation alignment %r.' % self.alignment)
        self.anchor = options.get('anchor') or None
        if self.anchor is not None and self.anchor not in source.dbm.obskeys:
            raise weeimport.weeimport.WeeImportOptionError('Unknown archive anchor %r.' % self.anchor)
        raw_shift = options.get('max_shift')
        self.max_shift = float(raw_shift) if raw_shift is not None else None
        if self.max_shift is not None and (not math.isfinite(self.max_shift) or self.max_shift < 0):
            raise weeimport.weeimport.WeeImportOptionError('max_shift must be a finite non-negative number of seconds.')
        if self.alignment != 'interval' and self.max_shift is None:
            raise weeimport.weeimport.WeeImportOptionError('Set max_shift explicitly for %s alignment.' % self.alignment)
        self._validate_fields()
        self.connection = sqlite3.connect(directory + '/aggregation.sdb')
        try:
            self.connection.execute('CREATE TABLE readings (stamp INTEGER PRIMARY KEY, data TEXT NOT NULL)')
            self.connection.execute('CREATE TABLE targets (stamp INTEGER PRIMARY KEY, start REAL, units INTEGER, data TEXT)')
            self.connection.execute('CREATE TABLE matched (target INTEGER, stamp INTEGER, data TEXT)')
            self.connection.execute('CREATE INDEX matched_target ON matched (target, stamp)')
            self.connection.execute('CREATE TABLE updates (stamp INTEGER PRIMARY KEY, data TEXT, before TEXT, samples INTEGER)')
        except Exception:
            self.connection.close()
            raise

    def _validate_fields(self):
        if not self.fields:
            raise weeimport.weeimport.WeeImportMapError('Map at least one observation for --updateagg.')
        schema = weewx.schemas.wview_extended.schema
        table = schema['table'] if isinstance(schema, dict) else schema
        standard = {field for field, definition in table} | set(weewx.accum.defaults_dict['Accumulator'])
        configured = self.source.config_dict.get('Accumulator', {})
        for field in self.fields:
            if field not in self.source.dbm.obskeys:
                raise weeimport.weeimport.WeeImportMapError('Mapped observation %r is not in the archive schema.' % field)
            if field not in standard and 'extractor' not in configured.get(field, {}):
                raise weeimport.weeimport.WeeImportMapError(
                    'Set [Accumulator][[%s]] extractor explicitly; a custom field name does not define aggregation.' % field)
            if field in WIND_FIELDS and 'windSpeed' not in self.fields:
                raise weeimport.weeimport.WeeImportMapError('Map windSpeed with %s to use WeeWX wind aggregation.' % field)
            try:
                weewx.accum.new_accumulator(field)
                weewx.accum.get_add_function(field)
                weewx.accum.get_extract_function(field)
            except KeyError as error:
                raise weeimport.weeimport.WeeImportMapError('Invalid accumulator configuration for %s: %s' % (field, error))

    def close(self):
        self.connection.close()

    def stage(self, records):
        """Convert and quality-check a mapped period without changing the archive.

        Args:
            records (Iterable[dict]): Records returned by the source's mapper.
        """
        for record in records:
            converted = weeimport.weeimport.to_std_system(record, self.source.archive_unit_sys)
            self.source.qc(converted, 'Archive')
            reading = {field: converted.get(field) for field in self.fields}
            reading.update(dateTime=converted['dateTime'], usUnits=converted['usUnits'])
            for field in self.fields:
                value = reading[field]
                if value is None or value == '':
                    reading[field] = None
                    continue
                accumulator = weewx.accum.new_accumulator(field)
                if isinstance(value, str) and type(accumulator) is weewx.accum.FirstLastAccum:
                    continue
                if not isinstance(value, (int, float)) or not math.isfinite(value):
                    raise weeimport.weeimport.WeeImportFieldError('Non-finite or non-numeric %s at %s.' % (field, reading['dateTime']))
            cursor = self.connection.execute('INSERT OR IGNORE INTO readings VALUES (?, ?)',
                                             (reading['dateTime'], json.dumps(reading, allow_nan=False)))
            self.counts['duplicates'] += not cursor.rowcount
        self.connection.commit()

    def _load_targets(self, archive, first, last):
        columns = ['dateTime', 'usUnits', 'interval'] + self.fields
        if self.anchor is not None and self.anchor not in columns:
            columns.append(self.anchor)
        if self.alignment == 'interval':
            condition = '`dateTime` >= ? AND `dateTime` - `interval` * 60 < ?'
            parameters = (first, last)
        else:
            condition = '`dateTime` >= ? AND `dateTime` <= ?'
            parameters = (first - self.max_shift, last + self.max_shift)
        if self.anchor is not None:
            condition += ' AND %s IS NOT NULL' % _quote(self.anchor)
        query = 'SELECT %s FROM %s WHERE %s ORDER BY `dateTime`' % (
            ', '.join(_quote(column) for column in columns), _quote(archive.table_name), condition)
        previous_stop = None
        for row in archive.genSql(query, parameters):
            record = dict(zip(columns, row))
            stop = record['dateTime']
            interval = record['interval']
            if not isinstance(stop, int) or not isinstance(interval, (int, float)) \
                    or not math.isfinite(interval) or interval <= 0:
                raise weeimport.weeimport.WeeImportFieldError('Invalid archive interval at %s.' % stop)
            start = stop - interval * 60
            if not math.isfinite(start):
                raise weeimport.weeimport.WeeImportFieldError('Archive interval overflows at %s.' % stop)
            if self.alignment == 'interval' and previous_stop is not None and start < previous_stop:
                raise weeimport.weeimport.WeeImportFieldError(
                    'Archive intervals overlap near %s. Repair them or choose an explicit archive anchor.' % stop)
            previous_stop = stop
            self.connection.execute('INSERT INTO targets VALUES (?, ?, ?, ?)',
                                    (stop, start, record['usUnits'], _encode(record)))

    def _match(self, stamp):
        following = self.connection.execute('SELECT stamp, start FROM targets WHERE stamp >= ? ORDER BY stamp LIMIT 1', (stamp,)).fetchone()
        if self.alignment == 'interval':
            target = following if following is not None and stamp > following[1] else None
        elif self.alignment == 'next':
            target = following
        else:
            previous = self.connection.execute('SELECT stamp, start FROM targets WHERE stamp <= ? ORDER BY stamp DESC LIMIT 1', (stamp,)).fetchone()
            if self.alignment == 'previous':
                target = previous
            else:
                candidates = {candidate[0]: candidate for candidate in (previous, following) if candidate is not None}
                if not candidates:
                    return None
                distance = min(abs(value - stamp) for value in candidates)
                if distance > self.max_shift:
                    return None
                nearest = [candidate for value, candidate in candidates.items() if abs(value - stamp) == distance]
                if len(nearest) != 1:
                    raise weeimport.weeimport.WeeImportFieldError('Equidistant archive destinations for %s.' % stamp)
                target = nearest[0]
        if target is not None and self.max_shift is not None and abs(target[0] - stamp) > self.max_shift:
            return None
        return target

    def prepare(self, archive):
        """Build all planned updates before any archive record can be changed.

        Args:
            archive (weewx.manager.Manager): Existing destination archive.
        """
        count, first, last = self.connection.execute('SELECT COUNT(*), MIN(stamp), MAX(stamp) FROM readings').fetchone()
        self.counts['readings'] = count
        if not count:
            return
        self._load_targets(archive, first, last)
        for stamp, data in self.connection.execute('SELECT stamp, data FROM readings ORDER BY stamp'):
            match = self._match(stamp)
            if match is None:
                self.counts['unmatched'] += 1
                continue
            target, start = match
            if (self.source.first_ts is not None and start < self.source.first_ts) \
                    or (self.source.last_ts is not None and target > self.source.last_ts):
                self.counts['outside_range'] += 1
                continue
            self.connection.execute('INSERT INTO matched VALUES (?, ?, ?)', (target, stamp, data))
        for target, start, units, before in self.connection.execute('SELECT stamp, start, units, data FROM targets ORDER BY stamp'):
            accumulator = weewx.accum.Accum(weeutil.weeutil.TimeSpan(start, target), units)
            present = set()
            samples = 0
            for data, in self.connection.execute('SELECT data FROM matched WHERE target = ? ORDER BY stamp', (target,)):
                reading = json.loads(data)
                if reading['usUnits'] != units:
                    raise weeimport.weeimport.WeeImportFieldError('Unit systems differ at destination %s.' % target)
                observations = {field for field in self.fields if reading[field] is not None}
                if reading.get('windSpeed') is None:
                    observations.discard('windDir')
                if reading.get('windSpeed') is None and reading.get('windGust') is None:
                    observations.discard('windGustDir')
                present.update(observations)
                # Explicit timestamp alignment changes labels, not the order of samples.
                reading['dateTime'] = target if self.alignment != 'interval' else reading['dateTime']
                accumulator.addRecord(reading, weight=1)
                samples += 1
            if not samples or not present:
                continue
            result = accumulator.getRecord()
            if not present.issubset(result):
                raise weeimport.weeimport.WeeImportFieldError('Accumulator did not produce mapped fields at %s: %s' % (target, ', '.join(sorted(present - set(result)))))
            values = {field: result[field] for field in self.fields if field in present and result[field] is not None}
            if not values:
                continue
            for field, value in values.items():
                if isinstance(value, float) and not math.isfinite(value):
                    raise weeimport.weeimport.WeeImportFieldError('Aggregation overflow for %s at %s.' % (field, target))
            values.update(dateTime=target, usUnits=units)
            self.connection.execute('INSERT INTO updates VALUES (?, ?, ?, ?)', (target, json.dumps(values, allow_nan=False), before, samples))
            self.counts['destinations'] += 1
            self.first_target = target if self.first_target is None else self.first_target
            self.last_target = target
        self.connection.commit()

    def preview(self):
        print('%d unique readings; %d existing archive intervals to update; %d unmatched; %d outside date limits; %d duplicate timestamps ignored.' % (
            self.counts['readings'], self.counts['destinations'], self.counts['unmatched'],
            self.counts['outside_range'], self.counts['duplicates']))
        for stamp, data, old, samples in self.connection.execute('SELECT stamp, data, before, samples FROM updates ORDER BY stamp LIMIT 20'):
            values = json.loads(data)
            before = json.loads(old)
            changes = ', '.join('%s: %s -> %s' % (field, _display(before[field]), _display(value))
                                for field, value in values.items() if field not in SPECIAL_FIELDS)
            print('  %s (%d readings): %s' % (weeutil.weeutil.timestamp_to_string(stamp), samples, changes))
        if self.counts['destinations'] > 20:
            print('Showing 20 of %d destination intervals. All readings were checked.' % self.counts['destinations'])

    def apply(self, archive):
        """Apply prepared observations without inserting rows or replacing interval metadata.

        Args:
            archive (weewx.manager.Manager): Destination archive.
        """
        tranche = []
        for data, in self.connection.execute('SELECT data FROM updates ORDER BY stamp'):
            tranche.append(json.loads(data))
            if len(tranche) >= self.source.tranche:
                archive.addRecord(tranche, update_only=True)
                tranche = []
        if tranche:
            archive.addRecord(tranche, update_only=True)


def run(source):
    """Import all periods before showing and applying an aggregation preview.

    Args:
        source (weeimport.weeimport.Source): Initialized source and destination manager.
    """
    with source.dbm as archive, tempfile.TemporaryDirectory(prefix='weewx-import-aggregation-') as directory:
        aggregation = ArchiveAggregation(source, directory)
        try:
            source.period_no = 1
            for period in source.period_generator():
                try:
                    raw = source.get_raw_data(period)
                except weeimport.weeimport.WeeImportDecodeError as error:
                    raise weeimport.weeimport.WeeImportIOError('Cannot decode import period %s: %s' % (period, error)) from error
                mapped = source.map_raw_data(raw, source.archive_unit_sys)
                aggregation.stage(mapped)
                aggregation.counts['duplicates'] += len(source.period_duplicates)
                source.period_duplicates = set()
                source.period_no += 1
            aggregation.prepare(archive)
            aggregation.preview()
            source.total_rec_proc = aggregation.counts['readings']
            source.total_unique_rec = aggregation.counts['destinations']
            source.earliest_ts = aggregation.first_target
            source.latest_ts = aggregation.last_target
            if source.dry_run:
                print('Dry run complete. No archive records changed.')
            elif aggregation.counts['destinations']:
                if not weeutil.weeutil.y_or_n('Apply these updates to existing archive records (y/n)? ', noprompt=source.no_prompt) == 'y':
                    print('Import cancelled. No archive records changed.')
                    return
                aggregation.apply(archive)
                print('Processed %d planned archive updates.' % aggregation.counts['destinations'])
        finally:
            aggregation.close()
