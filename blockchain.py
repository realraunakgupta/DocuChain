import hashlib
import json
import time

from db import blockchain_collection

class Block:
    def __init__(self, index, timestamp, document_type, issuer, document_hash, previous_hash, 
                 student_name=None, cert_id=None, validity=None, student_image=None):
        self.index = index
        self.timestamp = timestamp
        self.document_type = document_type
        self.issuer = issuer
        self.student_name = student_name or "Unknown Holder"
        self.cert_id = cert_id or "N/A"
        self.validity = validity or "Lifetime"
        self.student_image = student_image or ""
        self.document_hash = document_hash
        self.previous_hash = previous_hash
        self.block_hash = self.calculate_block_hash()

    def calculate_block_hash(self):
        block_string = json.dumps({
            "index": self.index,
            "timestamp": self.timestamp,
            "document_type": self.document_type,
            "issuer": self.issuer,
            "student_name": self.student_name,
            "cert_id": self.cert_id,
            "validity": self.validity,
            "student_image": self.student_image,
            "document_hash": self.document_hash,
            "previous_hash": self.previous_hash
        }, sort_keys=True).encode()
        return hashlib.sha256(block_string).hexdigest()

    def to_dict(self):
        return {
            "index": self.index,
            "timestamp": self.timestamp,
            "document_type": self.document_type,
            "issuer": self.issuer,
            "student_name": self.student_name,
            "cert_id": self.cert_id,
            "validity": self.validity,
            "student_image": self.student_image,
            "document_hash": self.document_hash,
            "previous_hash": self.previous_hash,
            "block_hash": self.block_hash
        }

    @classmethod
    def from_dict(cls, data):
        block = cls(
            data["index"],
            data["timestamp"],
            data["document_type"],
            data["issuer"],
            data["document_hash"],
            data["previous_hash"],
            data.get("student_name"),
            data.get("cert_id"),
            data.get("validity"),
            data.get("student_image")
        )
        block.block_hash = data.get("block_hash", block.calculate_block_hash())
        return block

class Blockchain:
    def __init__(self):
        self.chain = []
        self.load_chain()

    def load_chain(self):
        docs = list(blockchain_collection.find().sort([("index", 1)]))
        if docs:
            self.chain = [Block.from_dict(b) for b in docs]
        else:
            self.chain = []
            self.create_genesis_block()

    def save_chain(self):
        # We don't overwrite everything anymore. Instead, we insert blocks as we add them.
        pass

    def create_genesis_block(self):
        genesis_block = Block(0, time.time(), "Genesis", "System", "0", "0")
        self.chain.append(genesis_block)
        blockchain_collection.insert_one(genesis_block.to_dict())

    def get_latest_block(self):
        return self.chain[-1]

    def add_block(self, document_type, issuer, document_hash, 
                  student_name=None, cert_id=None, validity=None, student_image=None):
        previous_block = self.get_latest_block()
        new_block = Block(
            index=previous_block.index + 1,
            timestamp=time.time(),
            document_type=document_type,
            issuer=issuer,
            document_hash=document_hash,
            previous_hash=previous_block.block_hash,
            student_name=student_name,
            cert_id=cert_id,
            validity=validity,
            student_image=student_image
        )
        self.chain.append(new_block)
        blockchain_collection.insert_one(new_block.to_dict())
        return new_block

    def verify_chain(self):
        for i in range(1, len(self.chain)):
            current_block = self.chain[i]
            previous_block = self.chain[i-1]

            # Re-calculate hash to ensure block data wasn't changed
            if current_block.block_hash != current_block.calculate_block_hash():
                return False
            
            # Check if previous hash matches
            if current_block.previous_hash != previous_block.block_hash:
                return False
                
        return True

    def find_document_hash(self, document_hash):
        for block in self.chain:
            if block.document_hash == document_hash:
                return block
        return None
