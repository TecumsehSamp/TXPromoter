from __future__ import print_function

import argparse
import logging
import os
import random
import time
import traceback

import iota

logger = logging.getLogger('main')
sumlogger = logging.getLogger('success')


def setup_logging(name, summary=True):
    log_dir = os.path.join('logs', time.strftime("%d-%m-%Y"))
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    os.environ['TZ'] = 'Europe/Amsterdam'
    try:
        time.tzset()
    except:
        pass

    logger.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s | %(levelname)s | %(message)s', '%d.%m.%Y %H:%M:%S')

    ch = logging.StreamHandler()
    ch.setFormatter(formatter)
    logger.addHandler(ch)

    fh = logging.FileHandler(os.path.join(log_dir, time.strftime("%H%M%S") + "_" + name))
    fh.setFormatter(formatter)
    logger.addHandler(fh)

    if summary:
        fh = logging.FileHandler(os.path.join(log_dir, time.strftime("%H%M%S") + "_" + name + "_summary"))
        fh.setFormatter(formatter)
        sumlogger.setLevel(logging.INFO)
        sumlogger.addHandler(fh)


def get_depth():
    return random.randint(3, 14)


def is_confirmed(api, bundle_hash):
    try:
        tx_hashes = api.find_transactions([bundle_hash])['hashes']
    except:
        logger.error(traceback.format_exc())
        return

    bundle_states = []
    chunks = [tx_hashes[x:x + 1000] for x in range(0, len(tx_hashes), 1000)]
    for chunk in chunks:
        try:
            bundle_states += api.get_latest_inclusion(chunk)['states'].values()
        except:
            logger.error(traceback.format_exc())
            continue

    if any(confirmed is True for confirmed in bundle_states):
        return True


def promote(api, tx):
    try:
        promotable = api.helpers.is_promotable(tx.hash)
    except:
        logger.error(traceback.format_exc())
        return

    if promotable:
        try:
            logger.info('promoting tx: %s', tx.hash)
            api.promote_transaction(tx.hash, get_depth())
            logger.info('promoted successfully')
            return True
        except iota.adapter.BadApiResponse as err:
            logger.warning(err)
            logger.warning(traceback.format_exc())
            return
        except:
            logger.error(traceback.format_exc())
            return


def reattach(api, tx):
    try:
        reattachable = api.is_reattachable([tx.address])['reattachable'][0]
    except:
        logger.error(traceback.format_exc())
        return

    if reattachable:
        try:
            logger.info('reattaching tx: %s', tx.hash)
            api.replay_bundle(tx.hash, get_depth())
            logger.info('reattached successfully')
            return True
        except iota.adapter.BadApiResponse as err:
            logger.warning(err)
            logger.warning(traceback.format_exc())
            return
        except:
            logger.error(traceback.format_exc())
            return


def autopromote(api):
    while True:
        try:
            tips = api.get_tips()['hashes']
        except:
            logger.error(traceback.format_exc())
            time.sleep(60)
            continue

        logger.info('found %s tips', len(tips))

        trytes = []
        chunks = [tips[x:x + 1000] for x in range(0, len(tips), 1000)]
        for chunk in chunks:
            try:
                trytes += api.get_trytes(chunk)['trytes']
            except:
                logger.error(traceback.format_exc())
                continue

        for x in trytes:
            tx = iota.Transaction.from_tryte_string(x)
            if (tx.value > 1000 ** 2) and ((time.time() - tx.timestamp) < 60 * 60) and not is_confirmed(api, tx.bundle_hash):
                spam(api, None, tx, 45 * 60)


def spam(api, txid, trans=None, max_time=None):
    if txid is not None:
        try:
            tx_trytes = api.get_trytes([iota.TransactionHash(iota.TryteString(txid.encode('ascii')))])['trytes'][0]
        except:
            logger.error(traceback.format_exc())
            return
        input_tx = iota.Transaction.from_tryte_string(tx_trytes)
    else:
        input_tx = trans

    start_time = time.time()
    logger.info('start promoting tx (%smin, %smi): %s (%s)', round((start_time - input_tx.timestamp) / 60), round(input_tx.value / 1000 ** 2), input_tx.hash, input_tx.bundle_hash)

    count = 0
    max_count = 5
    sleeping = 0
    while True:
        if is_confirmed(api, input_tx.bundle_hash):
            logger.info('bundle confirmed: %s', input_tx.bundle_hash)
            sumlogger.info('Success: %smin - %smi: %s', round((time.time() - start_time) / 60), round(input_tx.value / 1000 ** 2), input_tx.bundle_hash)
            return

        try:
            tx_hashes = api.find_transactions([input_tx.bundle_hash])['hashes']
        except:
            logger.error(traceback.format_exc())
            time.sleep(60)
            continue

        logger.info('found %s tx in bundle. trying to promote/reattach', len(tx_hashes))

        tx_trytes = []
        chunks = [tx_hashes[x:x + 1000] for x in range(0, len(tx_hashes), 1000)]
        for chunk in chunks:
            try:
                tx_trytes += (api.get_trytes(chunk)['trytes'])
            except:
                logger.error(traceback.format_exc())
                continue

        txs = []
        for x in tx_trytes:
            txs.append(iota.Transaction.from_tryte_string(x))

        tails = list(filter(lambda x: x.is_tail, txs))
        tails = sorted(tails, key=lambda x: x.attachment_timestamp / 1000, reverse=True)[:min(len(tails), 10)]

        for tx in tails:
            if count < max_count:
                if promote(api, tx) and not sleeping:
                    sleeping = random.randint(1, 3)
            else:
                if reattach(api, tx):
                    if not sleeping:
                        sleeping = random.randint(1, 3)
                    break

        if count == max_count:
            count = 0
        else:
            count += 1

        logger.info('run finished. %s more runs until reattach', max_count - count)

        while sleeping > 0:
            logger.info('%s min wait...', sleeping)
            time.sleep(60)
            sleeping -= 1

        if max_time and ((time.time() - start_time) > max_time):
            logger.error('Did take too long (%s).. Skipping', round((time.time() - start_time) / 60))
            sumlogger.info('Timeout: %smin - %smi: %s', round((time.time() - start_time) / 60), round(input_tx.value / 1000 ** 2), input_tx.bundle_hash)
            return


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Promote / Reattach IOTA transaction')
    parser.add_argument('-tx')
    parser.add_argument('-lul')

    args = parser.parse_args()
    node = iota.Iota('http://localhost:14265')

    if args.tx is not None:
        setup_logging(args.tx, False)
        logger.info('------------------------Start------------------------')
        spam(node, args.tx, None, 3 * 60 * 60)
        logger.info('------------------------Finish------------------------')

    else:
        setup_logging('autopromote')
        logger.info('------------------------Starting Autopromote------------------------')
        autopromote(node)
