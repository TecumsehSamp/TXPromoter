from __future__ import print_function
import argparse
import iota
import logging
import os
import random
import sys
import time
import traceback

logger = logging.getLogger('main')
suclogger = logging.getLogger('success')
# TODO: Maybe not needed. Some bundles will make the api call throw (via remote at least) - just exclude them
badbundles = []

def setup_logging(name):

    logdir = os.path.join('logs', time.strftime("%d-%m-%Y"))
    if not os.path.exists(logdir):
        os.makedirs(logdir)
    
    os.environ['TZ'] = 'Europe/Amsterdam'
    try:
        time.tzset()
    except Exception:
        pass
    
    logger.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s | %(levelname)s | %(message)s', '%d.%m.%Y %H:%M:%S')

    ch = logging.StreamHandler()
    ch.setFormatter(formatter)
    logger.addHandler(ch)

    fh = logging.FileHandler(os.path.join(logdir,time.strftime("%H%M%S")+"_"+name))
    fh.setFormatter(formatter)
    logger.addHandler(fh)

    fh = logging.FileHandler(os.path.join(logdir,time.strftime("%H%M%S")+"_"+name+"_success"))
    fh.setFormatter(formatter)
    suclogger.addHandler(fh)

def get_depth():
    return random.randint(3,14)

def is_confirmed(api, bundlehash):
    try:
        txhashes = api.find_transactions([bundlehash])['hashes']
    except Exception as err:
        badbundles.append(bundlehash)
        logger.error(traceback.format_exc())
        raise

    try:
        bundlestates = api.get_latest_inclusion(txhashes)['states'].values()
    except Exception as err:
        badbundles.append(bundlehash)
        logger.error(traceback.format_exc())
        raise

    if any(confirmed == True for confirmed in bundlestates):        
        return True
    else:
        return False

def autopromote(api):
    while(True):
        try:
            tips = api.get_tips()['hashes']
        except Exception as err:
            logger.error(traceback.format_exc())
            continue

        chunksize = min(len(tips), 1000)

        logger.info('found %s tips - checking %s random tips', len(tips), chunksize)
        random.shuffle(tips)
        try:
            trytes = api.get_trytes(tips[:chunksize])['trytes']
        except Exception as err:
            logger.error(traceback.format_exc())
            continue

        for x in trytes:
            tx = iota.Transaction.from_tryte_string(x)
            if (tx.bundle_hash not in badbundles):
                try:
                    if ((tx.value > 1000**3) and ((time.time()-tx.timestamp) < 30 * 60) and not is_confirmed(api, tx.bundle_hash)):
                        promote(api, None, tx)
                except Exception:
                    pass

def promote(api, txid, trans=None):
    if (txid is not None):
        try:
            trytes = api.get_trytes([iota.TransactionHash(iota.TryteString(txid.encode('ascii')))])['trytes'][0]
        except Exception as err:
            logger.error(traceback.format_exc())
            return
        inputtx = iota.Transaction.from_tryte_string(trytes)
    else:
        inputtx = trans
    
    logger.info('start promoting tx (%smin): %s (%s)', round((time.time()-inputtx.timestamp)/60), inputtx.hash, inputtx.bundle_hash)
    
    count = 0
    maxCount = 3
    while (True):
        try:
            confirmed = is_confirmed(api, inputtx.bundle_hash)
        except Exception:
            break
        if (confirmed):
            logger.info('bundle confirmed: %s', inputtx.bundle_hash)
            suclogger(inputtx.bundle_hash)
            break

        try:
            txhashes = api.find_transactions([inputtx.bundle_hash])['hashes']
        except Exception as err:
            logger.error(traceback.format_exc())
            continue

        logger.info('found %s tx in bundle. trying to promote/reattach', len(txhashes))
        
        try:
            trytes = api.get_trytes(txhashes)['trytes']
        except Exception as err:
            logger.error(traceback.format_exc())
            continue

        for x in trytes:
            tx = iota.Transaction.from_tryte_string(x)

            if (tx.is_tail):
                if (count < maxCount):
                    try:
                        promotable = api.helpers.is_promotable(tx.hash)
                    except Exception as err:
                        logger.error(traceback.format_exc())
                        continue

                    if (promotable):
                        try:
                            logger.info('promoting tx: %s', tx.hash)
                            api.promote_transaction(tx.hash, get_depth())
                            logger.info('promoted successfully')
                        except Exception as err:
                            if('errors' in err.context):
                                if('inconsistent tips pair selected' in err.context['errors'][0]):
                                    pass
                                else:
                                    logger.error(traceback.format_exc())
                            else:
                                logger.error(traceback.format_exc())
                else:
                    try:
                        reattachable = api.is_reattachable([tx.address])['reattachable'][0]
                    except Exception as err:
                        logger.error(traceback.format_exc())
                        continue

                    if (reattachable):
                        try:
                            logger.info('reattaching tx: %s', tx.hash)
                            api.replay_bundle(tx.hash, get_depth())
                            logger.info('reattached successfully')
                            break
                        except Exception as err:
                            if('errors' in err.context):
                                if('inconsistent tips pair selected' in err.context['errors'][0]):
                                    pass
                                elif ('has invalid signature' in err.context['errors'][0]):
                                    badbundles.append(tx.bundle_hash)
                                    logger.error(err)
                                    return
                                else:
                                    logger.error(traceback.format_exc())
                            else:
                                logger.error(traceback.format_exc())
        
        if (count == maxCount):
            count = 0
        else:
            count += 1

        logger.info('finished. %s more runs until reattach', maxCount-count)
        sleeping = random.randint(0,2)
        while (sleeping > 0):
            logger.info('%s min sleep...', sleeping)
            time.sleep(60)
            sleeping -= 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Promote / Reattach IOTA transaction')
    parser.add_argument('-tx')

    args = parser.parse_args()
    api = iota.Iota('http://localhost:14265')

    if (args.tx is not None):
        setup_logging(args.tx)
        logger.info('------------------------Start------------------------')
        promote(api, args.tx)
        logger.info('------------------------Finish------------------------')
        
    else:
        setup_logging('autopromote')
        logger.info('------------------------Starting Autopromote------------------------')
        autopromote(api)
        logger.info('------------------------Finish Autopromote------------------------')
