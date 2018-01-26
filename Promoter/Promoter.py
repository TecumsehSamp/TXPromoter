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
    suclogger.setLevel(logging.INFO)
    suclogger.addHandler(fh)

def get_depth():
    return random.randint(3,14)

def is_confirmed(api, bundlehash):
    try:
        txhashes = api.find_transactions([bundlehash])['hashes']
    except:
        badbundles.append(bundlehash)
        logger.error(traceback.format_exc())
        raise

    try:
        bundlestates = api.get_latest_inclusion(txhashes)['states'].values()
    except:
        badbundles.append(bundlehash)
        logger.error(traceback.format_exc())
        raise

    if any(confirmed == True for confirmed in bundlestates):        
        return True
    else:
        return False

def promote(api, tx):
    try:
        promotable = api.helpers.is_promotable(tx.hash)
    except:
        logger.error(traceback.format_exc())
        raise

    if (promotable):
        try:
            logger.info('promoting tx: %s', tx.hash)
            api.promote_transaction(tx.hash, get_depth())
            logger.info('promoted successfully')
            return True
        except iota.adapter.BadApiResponse as err:
            if('inconsistent tips pair selected' in err.context['response']['errors'][0]):
                pass
            else:
                logger.error(traceback.format_exc())
            raise
        except:
            logger.error(traceback.format_exc())
            raise

def reattach(api, tx):
    try:
        reattachable = api.is_reattachable([tx.address])['reattachable'][0]
    except:
        logger.error(traceback.format_exc())
        raise

    if (reattachable):
        try:
            logger.info('reattaching tx: %s', tx.hash)
            api.replay_bundle(tx.hash, get_depth())
            logger.info('reattached successfully')
            return True
        except iota.adapter.BadApiResponse as err:
            if('inconsistent tips pair selected' in err.context['response']['errors'][0]):
                pass
            else:
                logger.error(traceback.format_exc())
            raise
        except:
            logger.error(traceback.format_exc())
            raise

def autopromote(api):
    while(True):
        try:
            tips = api.get_tips()['hashes']
        except:
            logger.error(traceback.format_exc())
            continue

        chunksize = min(len(tips), 1000)

        logger.info('found %s tips - checking %s random tips', len(tips), chunksize)
        random.shuffle(tips)
        try:
            trytes = api.get_trytes(tips[:chunksize])['trytes']
        except:
            logger.error(traceback.format_exc())
            continue

        for x in trytes:
            tx = iota.Transaction.from_tryte_string(x)
            if (tx.bundle_hash not in badbundles):
                try:
                    if ((tx.value > 1000**2) and ((time.time()-tx.timestamp) < 30 * 60) and not is_confirmed(api, tx.bundle_hash)):
                        spam(api, None, tx, 60*60)
                except:
                    logger.error(traceback.format_exc())
                    pass

def spam(api, txid, trans=None, maxTime=None):
    if (txid is not None):
        try:
            trytes = api.get_trytes([iota.TransactionHash(iota.TryteString(txid.encode('ascii')))])['trytes'][0]
        except:
            logger.error(traceback.format_exc())
            return
        inputtx = iota.Transaction.from_tryte_string(trytes)
    else:
        inputtx = trans
    
    startTime = time.time()
    logger.info('start promoting tx (%smin, %smi): %s (%s)', round((startTime-inputtx.timestamp)/60), round(inputtx.value/1000**2), inputtx.hash, inputtx.bundle_hash)
    
    count = 0
    maxCount = 5
    sleeping = 0
    while (True):
        try:
            confirmed = is_confirmed(api, inputtx.bundle_hash)
        except:
            break
        if (confirmed):
            logger.info('bundle confirmed: %s', inputtx.bundle_hash)
            suclogger.info('%smin - %smi: %s', round((time.time()-startTime)/60), round(inputtx.value/1000**2), inputtx.bundle_hash)
            break

        try:
            txhashes = api.find_transactions([inputtx.bundle_hash])['hashes']
        except:
            logger.error(traceback.format_exc())
            continue

        logger.info('found %s tx in bundle. trying to promote/reattach', len(txhashes))
        
        try:
            trytes = api.get_trytes(txhashes)['trytes']
        except:
            logger.error(traceback.format_exc())
            continue

        for x in trytes:
            tx = iota.Transaction.from_tryte_string(x)

            if (tx.is_tail):
                if (count < maxCount):
                    try:
                        if promote(api, tx) and not sleeping:
                                sleeping = random.randint(1,3)
                    except:
                        continue
                else:
                    try:
                        if reattach(api, tx):
                            if not sleeping:
                                sleeping = random.randint(1,3)
                            break
                    except:
                        continue

        if (count == maxCount):
            count = 0            
        else:
            count += 1

        logger.info('finished. %s more runs until reattach', maxCount-count)
        
        while (sleeping > 0):
            logger.info('%s min sleep...', sleeping)
            time.sleep(60)
            sleeping -= 1

        if (maxTime and ((time.time()-startTime) > maxTime)):
           logger.error('Did take too long (%s).. Will skip', round((time.time()-startTime)/60))
           break

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Promote / Reattach IOTA transaction')
    parser.add_argument('-tx')

    args = parser.parse_args()
    api = iota.Iota('http://localhost:14265')

    if (args.tx is not None):
        setup_logging(args.tx)
        logger.info('------------------------Start------------------------')
        spam(api, args.tx, 180*60)
        logger.info('------------------------Finish------------------------')
        
    else:
        setup_logging('autopromote')
        logger.info('------------------------Starting Autopromote------------------------')
        autopromote(api)
        logger.info('------------------------Finish Autopromote------------------------')