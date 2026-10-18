"""Provider boundaries; unavailable integrations never return fake success."""
from typing import Protocol
from dataclasses import dataclass
@dataclass(frozen=True)
class VerifiedPayment:
    provider: str
    reference: str
    invoice_id: int
    amount_minor: int
    currency: str
class PaymentProvider(Protocol):
    def create_checkout(self,invoice_id:int,idempotency_key:str)->str: ...
    def verify_webhook(self,body:bytes,headers:dict)->VerifiedPayment: ...
class ProvisioningProvider(Protocol):
    def health(self)->dict: ...
    def provision(self,contract:dict,idempotency_key:str)->str: ...
    def perform(self,reference:str,action:str,idempotency_key:str)->dict: ...
class IntegrationUnavailable(RuntimeError): pass

def payment_provider(name):
    raise IntegrationUnavailable(f'{name} adapter is not implemented. Use verified manual payment review.')
def provisioning_provider(name):
    raise IntegrationUnavailable('No provisioning provider is configured. Record actual manual fulfillment.')
