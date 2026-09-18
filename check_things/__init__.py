"""check_things — kiểm tra entity XML FBO.

Port từ extension fbo-autocomplete CheckingError:
- entity &name; dùng mà chưa khai báo trong DOCTYPE (kể cả transitive qua
  nội dung entity SYSTEM/inline).
- SYSTEM entity trỏ file không tồn tại trên đĩa.
- Optional source_roots: file/entity thiếu ở đây nhưng CÓ sẵn ở project nguồn.
"""

from .service import check_entities

__all__ = ["check_entities"]
