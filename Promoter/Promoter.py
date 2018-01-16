from __future__ import print_function
import argparse
import iota
import logging
import os
import random
import sys
import time

logger = logging.getLogger()

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

def autopromote(api):
    items = 100
    
    while(True):
        toPromote = []

        tips = api.get_tips()['hashes']
        logger.info('found %s tips - checking %s random tips', len(tips), items*5)
        random.shuffle(tips)
        ## TODO. *5 is too low if on running localhost!
        chunks = [tips[x:x+items] for x in range(0, items*5, items)]
        for chunk in chunks:
            for x in api.get_trytes(chunk)['trytes']:
                tx = iota.Transaction.from_tryte_string(x)
                ## should check if bundle is confirmed already and because this is done by looking at the bundle pass on bundlehash instead of tx to promote_tx
                if (tx.value > 1000**2 and (time.time()-tx.timestamp) > 20 * 60):
                    toPromote.append(tx)

        if (toPromote):
            logger.info('found %s worthy tx', len(toPromote))
            for x in toPromote:
                promote_tx(None,api,tx)

def promote_tx(txid, api, trans=None):
    if (txid is not None):
        inputtx = iota.Transaction.from_tryte_string(api.get_trytes([iota.TransactionHash(iota.TryteString(txid.encode('ascii')))])['trytes'][0])
    else:
        inputtx = trans
    logger.info('start promoting tx (%smin): %s', round((time.time()-inputtx.timestamp)/60), inputtx.hash)
    bundlehash = inputtx.bundle_hash
    logger.info('bundle: %s', bundlehash)

    count = 0
    maxCount = 5
    while (True):
        txhashes = api.find_transactions([bundlehash])['hashes']
        logger.info('found %s tx in bundle', len(txhashes))

        if any(confirmed == True for confirmed in api.get_latest_inclusion(txhashes)['states'].values()):
            logger.info('!!!tx confirmed!!!')
            break

        for x in api.get_trytes(txhashes)['trytes']:
            tx = iota.Transaction.from_tryte_string(x)

            if (tx.is_tail):
                if (count < maxCount):
                    try:
                        logger.info('promoting tx: %s', tx.hash)
                        promotiontx = api.promote_transaction(tx.hash, get_depth())['bundle'][0]
                        logger.debug('created tx: %s', promotiontx.hash)
                    except Exception as err:
                        logger.error(format(err))
                else:
                    if (api.is_reattachable([tx.address])['reattachable'][0]):
                        try:
                            logger.info('reattaching tx: %s', tx.hash)
                            reattachtx = api.replay_bundle(tx.hash,get_depth())['bundle'][0]
                            logger.debug('created tx: %s', reattachtx.hash)
                        except Exception as err:
                            logger.error(format(err))
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
        promote_tx(args.tx, api)
        logger.info('------------------------Finish------------------------')
        
    else:
        setup_logging('autopromote')
        logger.info('------------------------Starting Autopromote------------------------')
        autopromote(api)
        logger.info('------------------------Finish Autopromote------------------------')
