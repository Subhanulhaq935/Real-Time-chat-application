import uuid
from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload
from app.models.contact import Contact


class ContactRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_contact(self, owner_user_id: uuid.UUID, contact_user_id: uuid.UUID) -> Optional[Contact]:
        stmt = (
            select(Contact)
            .options(joinedload(Contact.contact_user))
            .where(
                Contact.owner_user_id == owner_user_id,
                Contact.contact_user_id == contact_user_id,
            )
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def list_contacts_by_owner(self, owner_user_id: uuid.UUID) -> List[Contact]:
        stmt = (
            select(Contact)
            .options(joinedload(Contact.contact_user))
            .where(Contact.owner_user_id == owner_user_id)
            .order_by(Contact.custom_name.asc())
        )
        return list(self.db.execute(stmt).scalars().all())

    def create_or_update_contact(
        self,
        owner_user_id: uuid.UUID,
        contact_user_id: uuid.UUID,
        custom_name: str,
    ) -> Contact:
        contact = self.get_contact(owner_user_id, contact_user_id)
        if contact:
            contact.custom_name = custom_name.strip()
        else:
            contact = Contact(
                owner_user_id=owner_user_id,
                contact_user_id=contact_user_id,
                custom_name=custom_name.strip(),
            )
            self.db.add(contact)

        self.db.commit()
        self.db.refresh(contact)
        return contact

    def delete_contact(self, owner_user_id: uuid.UUID, contact_user_id: uuid.UUID) -> bool:
        contact = self.get_contact(owner_user_id, contact_user_id)
        if not contact:
            return False
        self.db.delete(contact)
        self.db.commit()
        return True

