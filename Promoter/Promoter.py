from __future__ import print_function
import argparse
import iota
import logging
import os
import random
import sys
import time

logger = logging.getLogger()
# TODO: Maybe not needed. Bundles with huge amount of tx will crash the api call (remotely at least)
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

def get_depth():
    return random.randint(3,14)

def isConfirmed(api, bundlehash):
    try:
        txhashes = api.find_transactions([bundlehash])['hashes']
    except Exception as err:
        badbundles.append(bundlehash)
        logger.error('isConfirmed1')
        logger.error(format(err.context))
        return False

    try:
        bundlestates = api.get_latest_inclusion(txhashes)['states'].values()
    except Exception as err:
        logger.error('isConfirmed2')
        logger.error(format(err.context))
        return False

    if any(confirmed == True for confirmed in bundlestates):        
        return True

def autopromote(api):
    chunksize = 200
    chunkfactor = 5
    
    while(True):
        toPromote = []
        
        try:
            tips = api.get_tips()['hashes']
        except Exception as err:
            logger.error('autopromote1')
            logger.error(format(err.context))
            continue

        logger.info('found %s tips - checking %s random tips', len(tips), chunksize*chunkfactor)
        random.shuffle(tips)
        chunks = [tips[x:x+chunksize] for x in range(0, chunksize*chunkfactor, chunksize)]
        for chunk in chunks:            
            try:
                trytes = api.get_trytes(chunk)['trytes']
            except Exception as err:
                logger.error('autopromote2')
                logger.error(format(err.context))
                continue

            for x in trytes:
                tx = iota.Transaction.from_tryte_string(x)
                if (tx.bundle_hash not in badbundles):
                    if ((tx.value > 1000**2) and ((time.time()-tx.timestamp) > 20 * 60) and (not isConfirmed(api, tx.bundle_hash))):
                        toPromote.append(tx)

        if (toPromote):
            logger.info('found %s worthy tx', len(toPromote))
            for x in toPromote:
                promote(api, None, x)

def promote(api, txid, trans=None):
    if (txid is not None):
        try:
            trytes = api.get_trytes([iota.TransactionHash(iota.TryteString(txid.encode('ascii')))])['trytes'][0]
        except Exception as err:
            logger.error('promote1')
            logger.error(format(err.context))
            return
        inputtx = iota.Transaction.from_tryte_string(trytes)
    else:
        inputtx = trans
    
    logger.info('start promoting tx (%smin): %s (%s)', round((time.time()-inputtx.timestamp)/60), inputtx.hash, inputtx.bundle_hash)
    
    count = 0
    maxCount = 5
    while (True):
        if (isConfirmed(api, inputtx.bundle_hash)):
            logger.info('!!!tx confirmed!!!')
            break

        try:
            txhashes = api.find_transactions([inputtx.bundle_hash])['hashes']
        except Exception as err:
            logger.error('promote2')
            logger.error(format(err.context))
            continue

        logger.info('found %s tx in bundle', len(txhashes))
        
        try:
            trytes = api.get_trytes(txhashes)['trytes']
        except Exception as err:
            logger.error('promote3')
            logger.error(format(err.context))
            continue

        for x in trytes:
            tx = iota.Transaction.from_tryte_string(x)

            if (tx.is_tail):
                if (count < maxCount):
                    try:
                        logger.info('promoting tx: %s', tx.hash)
                        promotiontx = api.promote_transaction(tx.hash, get_depth())['bundle'][0]
                        logger.debug('created tx: %s', promotiontx.hash)
                    except Exception as err:
                        logger.error('promote4')
                        logger.error(format(err.context))
                else:
                    try:
                        reattachble = api.is_reattachable([tx.address])['reattachable'][0]
                    except Exception as err:
                        logger.error('promote5')
                        logger.error(format(err.context))
                        continue

                    if (reattachble):
                        try:
                            logger.info('reattaching tx: %s', tx.hash)
                            reattachtx = api.replay_bundle(tx.hash,get_depth())['bundle'][0]
                            logger.debug('created tx: %s', reattachtx.hash)
                        except Exception as err:
                            logger.error('promote6')
                            logger.error(format(err.context))
                        break
        
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
