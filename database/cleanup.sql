BEGIN
  FOR t IN (SELECT table_name FROM user_tables) LOOP
    BEGIN
      EXECUTE IMMEDIATE 'DROP TABLE ' || t.table_name || ' CASCADE CONSTRAINTS PURGE';
    EXCEPTION WHEN OTHERS THEN NULL;
    END;
  END LOOP;
  FOR s IN (SELECT sequence_name FROM user_sequences WHERE sequence_name NOT LIKE 'ISEQ$$%') LOOP
    BEGIN
      EXECUTE IMMEDIATE 'DROP SEQUENCE ' || s.sequence_name;
    EXCEPTION WHEN OTHERS THEN NULL;
    END;
  END LOOP;
  FOR p IN (SELECT object_name, object_type FROM user_objects WHERE object_type IN ('PROCEDURE','FUNCTION','VIEW')) LOOP
    BEGIN
      EXECUTE IMMEDIATE 'DROP ' || p.object_type || ' ' || p.object_name;
    EXCEPTION WHEN OTHERS THEN NULL;
    END;
  END LOOP;
END;
/
