import enum

from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    Date,
    Time,
    DateTime,
    ForeignKey,
    Enum as SAEnum,
    func,
)
from sqlalchemy.orm import relationship

from app.database import Base


class MaterialType(str, enum.Enum):
    material = "material"
    sample = "sample"


class HCPProfile(Base):
    """1. hcp_profiles: hcp_id, name, specialty."""

    __tablename__ = "hcp_profiles"

    hcp_id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, index=True)
    specialty = Column(String(255))

    interactions = relationship("Interaction", back_populates="hcp")
    tasks = relationship("Task", back_populates="hcp")


class Interaction(Base):
    """2. interactions: id, hcp_id, interaction_type, date, time,
    attendees, topics, sentiment, outcomes."""

    __tablename__ = "interactions"

    id = Column(Integer, primary_key=True, index=True)
    hcp_id = Column(Integer, ForeignKey("hcp_profiles.hcp_id"))
    interaction_type = Column(String(100))
    date = Column(Date)
    time = Column(Time)
    attendees = Column(Text)
    topics = Column(Text)
    sentiment = Column(String(50))
    outcomes = Column(Text)
    created_at = Column(DateTime(timezone=False), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=False), server_default=func.now(), onupdate=func.now()
    )

    hcp = relationship("HCPProfile", back_populates="interactions")
    materials_links = relationship(
        "InteractionMaterial", back_populates="interaction", cascade="all, delete-orphan"
    )
    tasks = relationship("Task", back_populates="interaction")


class Material(Base):
    """3. materials: material_id, name, type (Enum: 'material', 'sample')."""

    __tablename__ = "materials"

    material_id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, index=True)
    type = Column(SAEnum(MaterialType, name="material_type_enum"), nullable=False)

    interaction_links = relationship("InteractionMaterial", back_populates="material")


class InteractionMaterial(Base):
    """Join table: which materials/samples were shared in which interaction.

    Not explicitly named in the brief's 4-table list, but required to model a
    many-to-many relationship between interactions and materials without
    denormalizing the interactions table into repeated columns. See README
    "Design Notes" for rationale.
    """

    __tablename__ = "interaction_materials"

    id = Column(Integer, primary_key=True, index=True)
    interaction_id = Column(Integer, ForeignKey("interactions.id", ondelete="CASCADE"))
    material_id = Column(Integer, ForeignKey("materials.material_id", ondelete="CASCADE"))

    interaction = relationship("Interaction", back_populates="materials_links")
    material = relationship("Material", back_populates="interaction_links")


class Task(Base):
    """4. tasks: task_id, hcp_id, description, due_date."""

    __tablename__ = "tasks"

    task_id = Column(Integer, primary_key=True, index=True)
    hcp_id = Column(Integer, ForeignKey("hcp_profiles.hcp_id"))
    interaction_id = Column(Integer, ForeignKey("interactions.id"))
    description = Column(Text, nullable=False)
    due_date = Column(Date)
    created_at = Column(DateTime(timezone=False), server_default=func.now())

    hcp = relationship("HCPProfile", back_populates="tasks")
    interaction = relationship("Interaction", back_populates="tasks")
